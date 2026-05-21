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
    QFrame,
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
from ..core.preferences import apply_calibration_to_session, get_preferences
from ..core.svg_loader import load_svg
from ..hardware.controller import PlotterController
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
        self._prefs = get_preferences()

        self.setWindowTitle("brushplotter")
        self.resize(1280, 800)

        self._build_ui()
        self._build_menus()
        self._restore_preferences()
        self._update_state_indicators()

    def _restore_preferences(self):
        """Aplica las preferencias guardadas al estado inicial del UI."""
        # Geometría de ventana
        geom = self._prefs.get_window_geometry()
        if geom is not None:
            self.restoreGeometry(geom)

        # Material por defecto (con flags de agua del usuario)
        material_key = self._prefs.get_material_key()
        idx = self.material_combo.findData(material_key)
        if idx >= 0:
            # Bloqueamos señales para no disparar on_material_changed
            # antes de tener los demás controles listos.
            self.material_combo.blockSignals(True)
            self.material_combo.setCurrentIndex(idx)
            self.material_combo.blockSignals(False)

        # Recarga y velocidad
        self.recharge_spin.blockSignals(True)
        self.recharge_spin.setValue(self._prefs.get_recharge_cm())
        self.recharge_spin.blockSignals(False)

        self.speed_slider.blockSignals(True)
        self.speed_slider.setValue(self._prefs.get_speed_pendown())
        self.speed_slider.blockSignals(False)
        self._update_speed_label(self.speed_slider.value())

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
        panel.setFixedWidth(260)
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        from PySide6.QtWidgets import QScrollArea, QTabWidget
        from .output_config_panel import OutputConfigPanel

        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        # ─── Pestaña SALIDA ───
        output_tab = QWidget()
        output_scroll = QScrollArea()
        output_scroll.setWidgetResizable(True)
        output_scroll.setFrameShape(QFrame.Shape.NoFrame)
        output_layout = QVBoxLayout(output_tab)
        output_layout.setContentsMargins(12, 12, 12, 12)
        output_layout.setSpacing(8)

        self.output_panel = OutputConfigPanel()
        self.output_panel.layout_changed.connect(self.on_layout_changed)
        output_layout.addWidget(self.output_panel)
        output_layout.addStretch()

        output_scroll.setWidget(output_tab)
        tabs.addTab(output_scroll, "Salida")

        # ─── Pestaña MATERIAL + TINTEROS ───
        material_tab = QWidget()
        material_layout = QVBoxLayout(material_tab)
        material_layout.setContentsMargins(12, 12, 12, 12)
        material_layout.setSpacing(10)

        material_layout.addWidget(self._section_label("MATERIAL"))
        self.material_combo = QComboBox()
        for key, profile in DEFAULT_PROFILES.items():
            self.material_combo.addItem(profile.name, userData=key)
        self.material_combo.currentIndexChanged.connect(self.on_material_changed)
        material_layout.addWidget(self.material_combo)

        material_layout.addWidget(self._section_label("RECARGA CADA"))
        recharge_row = QHBoxLayout()
        self.recharge_spin = QDoubleSpinBox()
        self.recharge_spin.setRange(0.5, 50.0)
        self.recharge_spin.setSingleStep(0.5)
        self.recharge_spin.setSuffix(" cm")
        self.recharge_spin.setValue(12.7)  # 5 pulgadas
        self.recharge_spin.valueChanged.connect(self.on_recharge_changed)
        recharge_row.addWidget(self.recharge_spin)
        material_layout.addLayout(recharge_row)

        material_layout.addWidget(self._section_label("VELOCIDAD"))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 20)
        self.speed_slider.setValue(5)
        self.speed_slider.valueChanged.connect(self._update_speed_label)
        self.speed_slider.valueChanged.connect(self.on_speed_changed)
        material_layout.addWidget(self.speed_slider)
        self.speed_label = QLabel("Lenta · 5%")
        self.speed_label.setStyleSheet("font-size: 11px; color: #888;")
        material_layout.addWidget(self.speed_label)

        # Panel de tinteros
        self.inkwell_panel = InkwellPanel()
        self.inkwell_panel.edit_requested.connect(self.on_edit_inkwell)
        self.inkwell_panel.edit_water_requested.connect(self.on_edit_water)
        self.inkwell_panel.add_requested.connect(self.on_add_inkwell)
        self.inkwell_panel.toggle_water_before_dip.connect(
            self.on_toggle_water_before_dip
        )
        self.inkwell_panel.toggle_water_on_color_change.connect(
            self.on_toggle_water_on_color_change
        )
        material_layout.addWidget(self.inkwell_panel)
        material_layout.addStretch()

        tabs.addTab(material_tab, "Material y tinteros")

        outer.addWidget(tabs)
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
        plotter_menu.addAction(self.action_manual)

        prefs_menu = menubar.addMenu("Preferencias")
        reset_action = QAction("Restablecer preferencias…", self)
        reset_action.triggered.connect(self.on_reset_preferences)
        prefs_menu.addAction(reset_action)

    @Slot()
    def on_reset_preferences(self):
        ret = QMessageBox.question(
            self,
            "Restablecer preferencias",
            "Esto borrará todas las preferencias guardadas:\n\n"
            "• Plotter y material\n"
            "• Posiciones de tinteros y agua\n"
            "• Velocidad y recarga\n"
            "• Geometría de la ventana\n\n"
            "Los cambios se aplicarán la próxima vez que abras la app.\n\n"
            "¿Continuar?",
        )
        if ret == QMessageBox.StandardButton.Yes:
            self._prefs.reset_all()
            self._append_log("Preferencias restablecidas. Reinicia la app.")
            QMessageBox.information(
                self,
                "Preferencias restablecidas",
                "Cierra y vuelve a abrir la app para ver el efecto.",
            )

    # ----------------------------------------------------------
    # Slots
    # ----------------------------------------------------------
    @Slot()
    def on_open_svg(self):
        # Recordar última carpeta usada
        last_dir = self._prefs.get_last_svg_dir()
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir SVG",
            last_dir,
            "SVG (*.svg)",
        )
        if not path_str:
            return

        # Guardar la carpeta para la próxima vez
        from pathlib import Path
        self._prefs.set_last_svg_dir(str(Path(path_str).parent))

        try:
            session = load_svg(path_str)
        except Exception as e:
            QMessageBox.critical(self, "Error al cargar SVG", str(e))
            return

        self._session = session

        # Aplicar el material actualmente seleccionado en el combo
        from dataclasses import replace
        material_key = self.material_combo.currentData()
        if material_key and material_key in DEFAULT_PROFILES:
            session.material_profile = replace(DEFAULT_PROFILES[material_key])

        # Aplicar calibración guardada (tinteros, agua, flags)
        applied = apply_calibration_to_session(session, self._prefs)

        # Conectar el panel de salida (calcula layout y aplica al session)
        self.output_panel.set_session(session)

        self.canvas_view.load_session(session)
        self.inkwell_panel.set_session(session)

        # Dimensiones físicas en cm
        from ..core.units import inches_to_cm
        width_cm = inches_to_cm(session.canvas.drawing_width)
        height_cm = inches_to_cm(session.physical_height)
        self.strokes_label.setText(
            f"{len(session.strokes)} trazos · {len(session.colors)} colores\n"
            f"Salida: {width_cm:.1f} × {height_cm:.1f} cm"
        )
        self.progress_label.setText("0%")
        self.action_start.setEnabled(True)
        self._append_log(f"SVG cargado: {Path(path_str).name}")
        if applied > 0:
            self._append_log(
                f"Calibración recuperada para {applied} color(es)"
            )

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

        # Validación 0: ¿el layout cabe en la cama?
        layout = self.output_panel.get_current_layout()
        if layout is not None and not layout.fits:
            QMessageBox.warning(
                self,
                "El dibujo no cabe en la cama",
                f"{layout.message_short}\n\n"
                "Reduce la escala o cambia la orientación/tamaño de la cama "
                "antes de iniciar.",
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

        # Refinar el material_profile con los controles del UI.
        # NO reasignamos el perfil completo desde DEFAULT_PROFILES porque
        # el usuario puede haber tocado los checkboxes del agua, y se
        # perderían sus cambios.
        from ..core.units import cm_to_inches
        # El spinner está en cm — convertir a pulgadas
        self._session.material_profile.max_draw_distance_inches = (
            cm_to_inches(self.recharge_spin.value())
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
        self._worker.water_dip_started.connect(self.on_water_dip_started)
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

    @Slot()
    def on_water_dip_started(self):
        # Si el último evento del session log es deep_water_dip, mostramos
        # un mensaje específico; si no, es ritual rápido.
        if (
            self._session
            and self._session.event_log
            and self._session.event_log[-1].get("type") == "deep_water_dip"
        ):
            self._append_log("🌊 Limpieza profunda en agua")
        else:
            self._append_log("💧 Paso por agua")

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
            # Persistir GLOBALMENTE por nombre
            self._prefs.upsert_inkwell(new_color.name, new_color)
            self.inkwell_panel.set_session(self._session)
            self.canvas_view.load_session(self._session)
            self._append_log(f"Tintero editado: {new_color.name}")

    @Slot()
    def on_add_inkwell(self):
        """Añadir un nuevo tintero a la sesión.

        Si no hay sesión cargada, no hacer nada (no tiene sentido un
        tintero sin SVG). Si hay sesión, crear un tintero placeholder
        y abrir directamente el diálogo de edición.
        """
        if self._session is None:
            QMessageBox.information(
                self,
                "Sin SVG cargado",
                "Carga un SVG primero. Los tinteros se asocian a una sesión "
                "y a los colores que aparecen en el dibujo.",
            )
            return

        from .inkwell_edit_dialog import InkwellEditDialog
        from ..core.stroke_model import InkColor
        n = 1
        while f"tintero_{n}" in self._session.colors:
            n += 1
        new_id = f"tintero_{n}"
        placeholder = InkColor(name=f"Tintero {n}", hex="#888888")

        dlg = InkwellEditDialog(placeholder, self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            new_color = dlg.build_color()
            self._session.colors[new_id] = new_color
            # Persistir globalmente
            self._prefs.upsert_inkwell(new_color.name, new_color)
            self.inkwell_panel.set_session(self._session)
            self.canvas_view.load_session(self._session)
            self._append_log(f"Tintero añadido: {new_color.name}")

    @Slot()
    def on_edit_water(self):
        if self._session is None:
            return
        from .water_station_edit_dialog import WaterStationEditDialog
        dlg = WaterStationEditDialog(self._session.water_station, self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            self._session.water_station = dlg.build_water_station()
            # Persistir
            self._prefs.set_water_station(self._session.water_station)
            self.inkwell_panel.set_session(self._session)
            self.canvas_view.load_session(self._session)
            self._append_log("Estación de agua configurada")

    @Slot(bool)
    def on_toggle_water_before_dip(self, enabled: bool):
        self._prefs.set_uses_water_before_dip(enabled)
        if self._session is None:
            return
        self._session.material_profile.uses_water_before_dip = enabled
        self._append_log(
            f"Agua antes de recargar: {'activada' if enabled else 'desactivada'}"
        )

    @Slot(bool)
    def on_toggle_water_on_color_change(self, enabled: bool):
        self._prefs.set_uses_water_on_color_change(enabled)
        if self._session is None:
            return
        self._session.material_profile.uses_water_on_color_change = enabled
        self._append_log(
            f"Agua al cambiar color: {'activada' if enabled else 'desactivada'}"
        )

    @Slot()
    def on_material_changed(self):
        """Aplica el perfil del material seleccionado a la sesión activa.

        Esto cambia: distancia de recarga, velocidad, posiciones del
        pincel, y los dos flags de uso de agua (lo cual refresca los
        checkboxes del panel de agua).

        Guarda el material elegido en preferencias.
        """
        key = self.material_combo.currentData()
        if not key or key not in DEFAULT_PROFILES:
            return

        from ..core.units import inches_to_cm
        from dataclasses import replace
        new_profile = replace(DEFAULT_PROFILES[key])

        # Persistir elección
        self._prefs.set_material_key(key)
        self._prefs.set_uses_water_before_dip(new_profile.uses_water_before_dip)
        self._prefs.set_uses_water_on_color_change(
            new_profile.uses_water_on_color_change
        )

        # Actualizar los controles del panel (sin disparar señales)
        self.recharge_spin.blockSignals(True)
        self.recharge_spin.setValue(inches_to_cm(new_profile.max_draw_distance_inches))
        self.recharge_spin.blockSignals(False)
        self._prefs.set_recharge_cm(self.recharge_spin.value())

        self.speed_slider.blockSignals(True)
        self.speed_slider.setValue(new_profile.speed_pendown)
        self.speed_slider.blockSignals(False)
        self._update_speed_label(self.speed_slider.value())
        self._prefs.set_speed_pendown(new_profile.speed_pendown)

        # Aplicar al session si hay uno cargado
        if self._session is not None:
            self._session.material_profile = new_profile
            self.inkwell_panel.set_session(self._session)
            self._append_log(f"Material: {new_profile.name}")

    @Slot(float)
    def on_recharge_changed(self, value: float):
        self._prefs.set_recharge_cm(value)
        if self._session is not None:
            from ..core.units import cm_to_inches
            self._session.material_profile.max_draw_distance_inches = (
                cm_to_inches(value)
            )

    @Slot(int)
    def on_speed_changed(self, value: int):
        self._prefs.set_speed_pendown(value)
        if self._session is not None:
            self._session.material_profile.speed_pendown = value

    @Slot()
    def on_layout_changed(self):
        """Llamado por el OutputConfigPanel cada vez que cambia un parámetro.
        Refresca el preview con el nuevo layout."""
        if self._session is not None:
            self.canvas_view.load_session(self._session)
            # Actualizar la etiqueta de tamaño de salida en el panel derecho
            from ..core.units import inches_to_cm
            width_cm = inches_to_cm(self._session.canvas.drawing_width)
            height_cm = inches_to_cm(
                (self._session.svg_max_y - self._session.svg_min_y) * self._session.scale
            )
            self.strokes_label.setText(
                f"{len(self._session.strokes)} trazos · "
                f"{len(self._session.colors)} colores\n"
                f"Salida: {width_cm:.1f} × {height_cm:.1f} cm"
            )

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
        # Guardar geometría de ventana
        self._prefs.set_window_geometry(self.saveGeometry())
        self._prefs.sync()

        if self._worker:
            self._worker.request_stop()
            self._cleanup_worker()
        super().closeEvent(event)
