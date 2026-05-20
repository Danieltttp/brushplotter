"""Ventana principal de brushplotter.

Traducción del primer mockup. Layout:
    - Barra superior: nombre del archivo, botones Abrir / Calibrar / Iniciar
    - Panel izquierdo: material, distancia de recarga, velocidad, tinteros
    - Centro: CanvasView con preview del SVG
    - Panel derecho: estado, progreso, log

El worker corre en un QThread separado; las señales actualizan la UI.
"""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QStatusBar,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..core.stroke_model import (
    DEFAULT_PROFILES,
    PaintingSession,
)
from ..core.svg_loader import load_svg
from ..hardware.controller import PlotterController
from ..hardware.plotter_models import DEFAULT_MODEL_KEY, PLOTTER_MODELS, get_model
from ..hardware.simulator import SimulatedController
from ..workers.paint_worker import DipPattern, PaintWorker
from .canvas_view import CanvasView
from .inkwell_panel import InkwellPanel


# ----------------------------------------------------------
# Selección del controlador
# ----------------------------------------------------------
def make_controller(simulated: bool) -> PlotterController:
    """Crea el controlador real o simulado.

    Importa nextdraw_controller solo si hace falta (lazy import) para
    no requerir el SDK en entornos de desarrollo.
    """
    if simulated:
        return SimulatedController(speed_factor=0.05)
    # Lazy import del controlador real
    try:
        from ..hardware.nextdraw_controller import NextDrawController
    except ImportError as e:
        raise RuntimeError(
            "El SDK de NextDraw no está instalado. Instala con:\n"
            "pip install https://software-download.bantamtools.com/nd/api/nextdraw_api.zip"
        ) from e
    return NextDrawController()


class MainWindow(QMainWindow):
    """Ventana principal de la aplicación."""

    def __init__(self, simulated: bool = True, parent=None):
        super().__init__(parent)
        self._simulated = simulated
        self._session: PaintingSession | None = None
        self._worker: PaintWorker | None = None
        self._worker_thread: QThread | None = None
        self._session_start_time: float | None = None

        self.setWindowTitle("brushplotter")
        self.resize(1280, 800)

        self._build_ui()
        self._build_menus()
        self._update_state_indicators()

    # ----------------------------------------------------------
    # Construcción de la UI
    # ----------------------------------------------------------
    def _build_ui(self):
        # Barra de herramientas superior
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.action_open = QAction("Abrir SVG…", self)
        self.action_open.setShortcut(QKeySequence.StandardKey.Open)
        self.action_open.triggered.connect(self.on_open_svg)
        toolbar.addAction(self.action_open)

        self.action_calibrate = QAction("Calibrar…", self)
        self.action_calibrate.triggered.connect(self.on_calibrate)
        toolbar.addAction(self.action_calibrate)

        self.action_manual = QAction("Control manual…", self)
        self.action_manual.setShortcut("Ctrl+M")
        self.action_manual.triggered.connect(self.on_manual_control)
        toolbar.addAction(self.action_manual)

        toolbar.addSeparator()

        # Selector de modelo de plotter
        toolbar.addWidget(QLabel(" Plotter: "))
        self.plotter_combo = QComboBox()
        for key, model in PLOTTER_MODELS.items():
            self.plotter_combo.addItem(model.name, userData=key)
        idx = self.plotter_combo.findData(DEFAULT_MODEL_KEY)
        if idx >= 0:
            self.plotter_combo.setCurrentIndex(idx)
        self.plotter_combo.currentIndexChanged.connect(self.on_plotter_model_changed)
        toolbar.addWidget(self.plotter_combo)

        toolbar.addSeparator()

        self.action_start = QAction("▶ Iniciar", self)
        self.action_start.triggered.connect(self.on_start)
        self.action_start.setEnabled(False)
        toolbar.addAction(self.action_start)

        self.action_pause = QAction("⏸ Pausar", self)
        self.action_pause.triggered.connect(self.on_pause)
        self.action_pause.setEnabled(False)
        toolbar.addAction(self.action_pause)

        self.action_stop = QAction("■ Parar", self)
        self.action_stop.triggered.connect(self.on_stop)
        self.action_stop.setEnabled(False)
        toolbar.addAction(self.action_stop)

        # Layout central de tres columnas
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Columna izquierda: configuración
        left = self._build_left_panel()
        main_layout.addWidget(left)

        # Centro: vista del lienzo
        self.canvas_view = CanvasView()
        main_layout.addWidget(self.canvas_view, stretch=1)

        # Columna derecha: estado y log
        right = self._build_right_panel()
        main_layout.addWidget(right)

        # Barra de estado
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        mode = "SIMULADO" if self._simulated else "Hardware NextDraw"
        self.status_bar.showMessage(f"Modo: {mode}")

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(220)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        layout.addWidget(self._section_label("MATERIAL"))
        self.material_combo = QComboBox()
        for key, profile in DEFAULT_PROFILES.items():
            self.material_combo.addItem(profile.name, userData=key)
        self.material_combo.currentIndexChanged.connect(self.on_material_changed)
        layout.addWidget(self.material_combo)

        layout.addWidget(self._section_label("RECARGA CADA"))
        recharge_row = QHBoxLayout()
        self.recharge_spin = QDoubleSpinBox()
        self.recharge_spin.setRange(0.5, 20.0)
        self.recharge_spin.setSingleStep(0.5)
        self.recharge_spin.setSuffix(" pulg.")
        self.recharge_spin.setValue(5.0)
        recharge_row.addWidget(self.recharge_spin)
        layout.addLayout(recharge_row)

        layout.addWidget(self._section_label("VELOCIDAD"))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 20)
        self.speed_slider.setValue(5)
        self.speed_slider.valueChanged.connect(self._update_speed_label)
        layout.addWidget(self.speed_slider)
        self.speed_label = QLabel("Lenta · 5%")
        self.speed_label.setStyleSheet("font-size: 11px; color: #888;")
        layout.addWidget(self.speed_label)

        # Panel de tinteros
        self.inkwell_panel = InkwellPanel()
        self.inkwell_panel.edit_requested.connect(self.on_edit_inkwell)
        layout.addWidget(self.inkwell_panel)

        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(240)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        layout.addWidget(self._section_label("PROGRESO"))
        self.progress_label = QLabel("—")
        self.progress_label.setStyleSheet("font-size: 22px; font-weight: 500;")
        layout.addWidget(self.progress_label)

        self.strokes_label = QLabel("Sin SVG cargado")
        self.strokes_label.setStyleSheet("font-size: 11px; color: #888;")
        layout.addWidget(self.strokes_label)

        layout.addSpacing(8)

        self.time_label = self._kv_label("Tiempo", "00:00:00")
        layout.addLayout(self.time_label["row"])

        self.dips_label = self._kv_label("Recargas", "0")
        layout.addLayout(self.dips_label["row"])

        self.color_label = self._kv_label("Color activo", "—")
        layout.addLayout(self.color_label["row"])

        layout.addSpacing(8)
        layout.addWidget(self._section_label("REGISTRO"))

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet(
            "font-family: 'Menlo', 'Courier New', monospace; "
            "font-size: 10px; background: #f5f5f3; color: #333;"
        )
        layout.addWidget(self.log_view, stretch=1)

        return panel

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-size: 11px; color: #999; letter-spacing: 0.05em;"
        )
        return lbl

    def _kv_label(self, key: str, initial_value: str) -> dict:
        row = QHBoxLayout()
        k = QLabel(key)
        k.setStyleSheet("font-size: 11px; color: #888;")
        v = QLabel(initial_value)
        v.setStyleSheet("font-size: 11px; font-family: 'Menlo', 'Courier New', monospace;")
        v.setAlignment(Qt.AlignmentFlag.AlignRight)
        row.addWidget(k)
        row.addWidget(v)
        return {"row": row, "value": v}

    def _build_menus(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("Archivo")
        file_menu.addAction(self.action_open)
        file_menu.addSeparator()
        quit_action = QAction("Salir", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        plotter_menu = menubar.addMenu("Plotter")
        plotter_menu.addAction(self.action_calibrate)

    # ----------------------------------------------------------
    # Slots
    # ----------------------------------------------------------
    @Slot()
    def on_open_svg(self):
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir SVG",
            "",
            "SVG (*.svg)",
        )
        if not path_str:
            return
        try:
            session = load_svg(path_str)
        except Exception as e:
            QMessageBox.critical(self, "Error al cargar SVG", str(e))
            return

        self._session = session

        # Aplicar plotter actual a la sesión recién cargada
        model_key = self.plotter_combo.currentData() or DEFAULT_MODEL_KEY
        model = get_model(model_key)
        session.canvas.plotter_max_x = model.max_x_inches
        session.canvas.plotter_max_y = model.max_y_inches

        self.canvas_view.load_session(session)
        self.inkwell_panel.set_session(session)

        # Dimensiones físicas en cm (más legible que mm para el lienzo entero)
        width_cm = (session.canvas.drawing_width * 25.4) / 10
        height_cm = (session.physical_height * 25.4) / 10
        self.strokes_label.setText(
            f"{len(session.strokes)} trazos · {len(session.colors)} colores\n"
            f"Salida: {width_cm:.1f} × {height_cm:.1f} cm"
        )
        self.progress_label.setText("0%")
        self.action_start.setEnabled(True)
        self._append_log(f"SVG cargado: {Path(path_str).name}")

    @Slot()
    def on_calibrate(self):
        # Placeholder: el diálogo de calibración va en su propio módulo.
        QMessageBox.information(
            self,
            "Calibración",
            "El diálogo de calibración se abrirá aquí en la próxima versión.",
        )

    @Slot()
    def on_manual_control(self):
        if self._worker is not None:
            QMessageBox.warning(
                self,
                "Sesión en curso",
                "No se puede abrir el control manual mientras hay una "
                "sesión de pintura en curso. Pausa o para la sesión primero.",
            )
            return
        from .manual_control_dialog import ManualControlDialog
        try:
            controller = make_controller(simulated=self._simulated)
        except Exception as e:
            QMessageBox.critical(self, "Error de controlador", str(e))
            return
        dlg = ManualControlDialog(controller, self._session, self)
        dlg.show()  # no modal, queda como ventana flotante

    @Slot()
    def on_start(self):
        if self._session is None:
            return

        # Validación 1: ¿hay trazos con color asignado?
        unassigned = self._session.unassigned_stroke_count
        total = len(self._session.strokes)
        with_color = total - unassigned

        if with_color == 0:
            QMessageBox.warning(
                self,
                "Ningún trazo se pintaría",
                f"El SVG tiene {total} trazos pero ninguno tiene color asignado.\n\n"
                "Posibles causas:\n"
                "• Los paths del SVG no tienen atributo stroke=\"#color\".\n"
                "• Todos los strokes son negro (que se ignora por defecto).\n"
                "• El SVG no se cargó correctamente.\n\n"
                "Solución temporal: edita el SVG en Inkscape y asígnale "
                "colores a los trazos antes de cargarlo.",
            )
            return

        if unassigned > 0:
            ret = QMessageBox.question(
                self,
                "Trazos sin color",
                f"{unassigned} de {total} trazos no tienen color asignado y "
                f"se saltarán.\n\n¿Continuar con los {with_color} restantes?",
            )
            if ret != QMessageBox.StandardButton.Yes:
                return

        # Validación 2: tinteros sin calibrar para colores usados
        uncal = self._session.uncalibrated_colors
        if uncal:
            names = "\n  · ".join(c.name for c in uncal)
            QMessageBox.warning(
                self,
                "Tinteros sin calibrar",
                f"Los siguientes colores no tienen posición de tintero asignada:\n\n"
                f"  · {names}\n\n"
                f"Pulsa el botón ✎ junto a cada color en el panel izquierdo "
                f"para asignarle coordenadas, o usa 'Calibrar…' (próximamente).",
            )
            return

        # Aplicar parámetros del UI a la sesión
        material_key = self.material_combo.currentData()
        self._session.material_profile = DEFAULT_PROFILES[material_key]
        self._session.material_profile.max_draw_distance_inches = (
            self.recharge_spin.value()
        )
        self._session.material_profile.speed_pendown = self.speed_slider.value()

        # Crear controlador y worker
        try:
            controller = make_controller(simulated=self._simulated)
        except Exception as e:
            QMessageBox.critical(self, "Error de controlador", str(e))
            return

        self._worker = PaintWorker(self._session, controller)
        self._worker_thread = QThread()
        self._worker.moveToThread(self._worker_thread)

        # Conectar señales
        self._worker.stroke_started.connect(self.canvas_view.mark_stroke_drawing)
        self._worker.stroke_finished.connect(self.canvas_view.mark_stroke_done)
        self._worker.position_changed.connect(self.canvas_view.update_head_position)
        self._worker.progress_changed.connect(self.on_progress)
        self._worker.dip_started.connect(self.on_dip_started)
        self._worker.color_change_requested.connect(self.on_color_change)
        self._worker.finished.connect(self.on_worker_finished)
        self._worker.error.connect(self.on_worker_error)
        self._worker_thread.started.connect(self._worker.run)

        self._session_start_time = time.time()
        self._dip_count = 0
        self.action_start.setEnabled(False)
        self.action_pause.setEnabled(True)
        self.action_stop.setEnabled(True)
        self.action_open.setEnabled(False)
        self._append_log("Iniciando pintura…")

        self._worker_thread.start()

    @Slot()
    def on_pause(self):
        if self._worker:
            self._worker.request_pause()
            self._append_log("Pausa solicitada")

    @Slot()
    def on_stop(self):
        if self._worker:
            self._worker.request_stop()
            self._append_log("Parada solicitada")

    @Slot(float)
    def on_progress(self, fraction: float):
        pct = int(fraction * 100)
        self.progress_label.setText(f"{pct}%")
        if self._session_start_time:
            elapsed = int(time.time() - self._session_start_time)
            h, rem = divmod(elapsed, 3600)
            m, s = divmod(rem, 60)
            self.time_label["value"].setText(f"{h:02d}:{m:02d}:{s:02d}")

    @Slot(str)
    def on_dip_started(self, color_id: str):
        self._dip_count += 1
        self.dips_label["value"].setText(str(self._dip_count))
        if self._session and color_id in self._session.colors:
            name = self._session.colors[color_id].name
            self._append_log(f"Recarga · {name}")

    @Slot(str, str)
    def on_color_change(self, old_id: str, new_id: str):
        if not self._session:
            return
        new_name = self._session.colors[new_id].name
        if old_id:
            old_name = self._session.colors[old_id].name
            msg = (
                f"Cambio de color: {old_name} → {new_name}\n\n"
                f"Limpia el pincel, cárgalo con el nuevo color "
                f"y pulsa Continuar."
            )
        else:
            msg = (
                f"Iniciando con: {new_name}\n\n"
                f"Verifica que el pincel está cargado y pulsa Continuar."
            )
        self.color_label["value"].setText(new_name)
        self._append_log(f"⏸ Cambio de color → {new_name}")
        QMessageBox.information(self, "Cambio de color", msg)
        if self._worker:
            self._worker.acknowledge_color_change()

    @Slot()
    def on_worker_finished(self):
        self._append_log("Sesión terminada")
        self._cleanup_worker()
        self.action_start.setEnabled(True)
        self.action_pause.setEnabled(False)
        self.action_stop.setEnabled(False)
        self.action_open.setEnabled(True)

    @Slot(str)
    def on_worker_error(self, msg: str):
        self._append_log(f"ERROR: {msg}")
        QMessageBox.critical(self, "Error", msg)
        self._cleanup_worker()
        self.action_start.setEnabled(True)
        self.action_pause.setEnabled(False)
        self.action_stop.setEnabled(False)
        self.action_open.setEnabled(True)

    @Slot(str)
    def on_edit_inkwell(self, color_id: str):
        if self._session is None or color_id not in self._session.colors:
            return
        from .inkwell_edit_dialog import InkwellEditDialog
        dlg = InkwellEditDialog(self._session.colors[color_id], self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            new_color = dlg.build_color()
            self._session.colors[color_id] = new_color
            self.inkwell_panel.set_session(self._session)
            self.canvas_view.load_session(self._session)
            self._append_log(f"Tintero editado: {new_color.name}")

    @Slot()
    def on_material_changed(self):
        key = self.material_combo.currentData()
        if key and key in DEFAULT_PROFILES:
            profile = DEFAULT_PROFILES[key]
            self.recharge_spin.setValue(profile.max_draw_distance_inches)
            self.speed_slider.setValue(profile.speed_pendown)

    @Slot()
    def on_plotter_model_changed(self):
        """Actualiza los límites de la cama según el plotter elegido."""
        key = self.plotter_combo.currentData()
        if not key:
            return
        model = get_model(key)
        if self._session is not None:
            self._session.canvas.plotter_max_x = model.max_x_inches
            self._session.canvas.plotter_max_y = model.max_y_inches
            self.canvas_view.load_session(self._session)
            self._append_log(f"Plotter: {model.name}")

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------
    def _cleanup_worker(self):
        if self._worker_thread:
            self._worker_thread.quit()
            self._worker_thread.wait(3000)
            self._worker_thread = None
            self._worker = None

    def _append_log(self, text: str):
        timestamp = time.strftime("%H:%M:%S")
        self.log_view.append(f"{timestamp}  {text}")

    def _update_speed_label(self, value: int):
        self.speed_label.setText(f"{'Lenta' if value < 10 else 'Rápida'} · {value}%")

    def _update_state_indicators(self):
        pass  # placeholder para indicadores futuros

    def closeEvent(self, event):
        if self._worker:
            self._worker.request_stop()
            self._cleanup_worker()
        super().closeEvent(event)
