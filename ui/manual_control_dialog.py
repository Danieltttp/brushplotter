"""Diálogo de control manual del plotter.

Permite al usuario operar la máquina antes/después de una sesión:
calibrar tinteros, probar el ritual de recarga, mover el cabezal,
hacer home, apagar motores.

Captura las flechas del teclado para jog rápido (paso configurable).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Slot
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..core.stroke_model import (
    InkColor,
    PaintingSession,
    Point,
    inches_to_mm,
    mm_to_inches,
)
from ..hardware.controller import PlotterController
from ..workers.manual_control_worker import ManualControlWorker


# Pasos de jog en mm (lo que ve el usuario)
JOG_STEPS_MM = [0.1, 1.0, 5.0, 10.0]


class ManualControlDialog(QDialog):
    """Diálogo de control manual.

    Recibe el controlador (ya creado por la ventana principal) y la
    sesión actual (para conocer los tinteros calibrados).
    """

    def __init__(
        self,
        controller: PlotterController,
        session: PaintingSession | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Control manual")
        self.setMinimumSize(560, 460)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        self._controller = controller
        self._session = session
        self._jog_step_mm = 1.0  # paso por defecto
        self._position = Point(0.0, 0.0)
        self._pen_down = False
        self._connected = False

        self._build_ui()
        self._start_worker()

    # ----------------------------------------------------------
    # Construcción de UI
    # ----------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Cabecera con estado de conexión
        header = QHBoxLayout()
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #aaa; font-size: 14px;")
        header.addWidget(self.status_dot)
        self.status_label = QLabel("Conectando…")
        self.status_label.setStyleSheet("font-size: 12px;")
        header.addWidget(self.status_label)
        header.addStretch()
        layout.addLayout(header)

        # Línea divisoria
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # Dos columnas
        cols = QHBoxLayout()
        cols.setSpacing(20)

        # ── Columna izquierda: posición + jog ──
        left_col = QVBoxLayout()

        left_col.addWidget(self._section_label("POSICIÓN DEL CABEZAL"))
        self.pos_label = QLabel("X: ——  Y: ——")
        self.pos_label.setStyleSheet(
            "font-family: 'Menlo', monospace; font-size: 14px; "
            "padding: 8px; background: #f5f5f3; border-radius: 4px;"
        )
        left_col.addWidget(self.pos_label)

        left_col.addSpacing(8)
        left_col.addWidget(self._section_label("MOVER CABEZAL"))
        left_col.addWidget(self._build_jog_grid())

        left_col.addSpacing(4)
        left_col.addWidget(self._section_label("PASO DE MOVIMIENTO"))
        left_col.addWidget(self._build_step_selector())
        hint = QLabel("Usa las flechas del teclado")
        hint.setStyleSheet("font-size: 10px; color: #888; padding-left: 4px;")
        left_col.addWidget(hint)

        left_col.addSpacing(8)
        left_col.addLayout(self._build_pen_buttons())

        left_col.addStretch()
        cols.addLayout(left_col, stretch=1)

        # ── Columna derecha: acciones ──
        right_col = QVBoxLayout()

        right_col.addWidget(self._section_label("IR A POSICIÓN"))

        # Coordenadas manuales (mm)
        goto_row = QHBoxLayout()
        self.goto_x = QDoubleSpinBox()
        self.goto_x.setRange(0, 1000)
        self.goto_x.setSuffix(" mm")
        self.goto_x.setDecimals(1)
        self.goto_y = QDoubleSpinBox()
        self.goto_y.setRange(0, 1000)
        self.goto_y.setSuffix(" mm")
        self.goto_y.setDecimals(1)
        goto_row.addWidget(QLabel("X"))
        goto_row.addWidget(self.goto_x)
        goto_row.addWidget(QLabel("Y"))
        goto_row.addWidget(self.goto_y)
        right_col.addLayout(goto_row)

        btn_goto = QPushButton("Ir a estas coordenadas")
        btn_goto.clicked.connect(self.on_go_to_coords)
        right_col.addWidget(btn_goto)

        right_col.addSpacing(8)

        btn_home = QPushButton("⌂  Ir a Home (0,0)")
        btn_home.clicked.connect(self.on_home)
        right_col.addWidget(btn_home)

        right_col.addSpacing(12)
        right_col.addWidget(self._section_label("TINTEROS"))

        # Dropdown de tinteros + botones
        self.inkwell_combo = QComboBox()
        self._refresh_inkwell_combo()
        right_col.addWidget(self.inkwell_combo)

        btn_goto_ink = QPushButton("⌖  Ir al tintero seleccionado")
        btn_goto_ink.clicked.connect(self.on_go_to_inkwell)
        right_col.addWidget(btn_goto_ink)

        btn_dip_test = QPushButton("🧪  Probar ritual de recarga")
        btn_dip_test.setToolTip(
            "Reproduce el movimiento completo de recarga (dip + stir + bob) "
            "sobre el tintero seleccionado, sin pintar.\nIMPORTANTE: usar "
            "sin pincel cargado o con el portaherramientas levantado."
        )
        btn_dip_test.clicked.connect(self.on_dip_test)
        right_col.addWidget(btn_dip_test)

        right_col.addSpacing(12)
        right_col.addWidget(self._section_label("MOTORES"))
        motors_row = QHBoxLayout()
        btn_motors_off = QPushButton("⏻  Apagar")
        btn_motors_off.setToolTip(
            "Apaga los motores XY para poder mover el cabezal a mano."
        )
        btn_motors_off.clicked.connect(self.on_motors_off)
        motors_row.addWidget(btn_motors_off)
        btn_motors_on = QPushButton("⚡  Encender")
        btn_motors_on.clicked.connect(self.on_motors_on)
        motors_row.addWidget(btn_motors_on)
        right_col.addLayout(motors_row)

        right_col.addStretch()
        cols.addLayout(right_col, stretch=1)

        layout.addLayout(cols)

        # Pie con botón cerrar
        layout.addStretch()
        footer = QHBoxLayout()
        footer.addStretch()
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.close)
        footer.addWidget(btn_close)
        layout.addLayout(footer)

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-size: 10px; color: #999; letter-spacing: 0.05em; "
            "margin-top: 4px; margin-bottom: 4px;"
        )
        return lbl

    def _build_jog_grid(self) -> QWidget:
        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(4)
        grid.setContentsMargins(0, 0, 0, 0)

        btn_up = QPushButton("↑")
        btn_up.clicked.connect(lambda: self._jog(0, -1))
        grid.addWidget(btn_up, 0, 1)

        btn_left = QPushButton("←")
        btn_left.clicked.connect(lambda: self._jog(-1, 0))
        grid.addWidget(btn_left, 1, 0)

        btn_home_grid = QPushButton("⌂")
        btn_home_grid.setToolTip("Ir a Home (0,0)")
        btn_home_grid.clicked.connect(self.on_home)
        grid.addWidget(btn_home_grid, 1, 1)

        btn_right = QPushButton("→")
        btn_right.clicked.connect(lambda: self._jog(1, 0))
        grid.addWidget(btn_right, 1, 2)

        btn_down = QPushButton("↓")
        btn_down.clicked.connect(lambda: self._jog(0, 1))
        grid.addWidget(btn_down, 2, 1)

        # Tamaño homogéneo
        for btn in [btn_up, btn_down, btn_left, btn_right, btn_home_grid]:
            btn.setFixedSize(50, 40)
            btn.setStyleSheet("font-size: 16px;")

        # Centrar el grid en su contenedor
        wrapper = QWidget()
        wrapper_layout = QHBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.addStretch()
        wrapper_layout.addWidget(container)
        wrapper_layout.addStretch()
        return wrapper

    def _build_step_selector(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._step_group = QButtonGroup(self)
        for step in JOG_STEPS_MM:
            btn = QRadioButton(f"{step:g} mm" if step >= 1 else f"{step} mm")
            btn.setStyleSheet("font-family: 'Menlo', monospace; font-size: 11px;")
            if step == self._jog_step_mm:
                btn.setChecked(True)
            btn.toggled.connect(
                lambda checked, s=step: self._set_jog_step(s) if checked else None
            )
            self._step_group.addButton(btn)
            layout.addWidget(btn)

        return container

    def _build_pen_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        btn_up = QPushButton("↥  Subir pincel")
        btn_up.clicked.connect(self.on_pen_up)
        row.addWidget(btn_up)
        btn_down = QPushButton("↧  Bajar pincel")
        btn_down.clicked.connect(self.on_pen_down)
        row.addWidget(btn_down)
        return row

    def _refresh_inkwell_combo(self):
        self.inkwell_combo.clear()
        if not self._session or not self._session.colors:
            self.inkwell_combo.addItem("(no hay tinteros)")
            self.inkwell_combo.setEnabled(False)
            return
        self.inkwell_combo.setEnabled(True)
        for cid, color in self._session.colors.items():
            if color.is_calibrated:
                ink = color.inkwell_position
                label = (
                    f"{color.name}  ·  "
                    f"{inches_to_mm(ink.x):.1f}, {inches_to_mm(ink.y):.1f} mm"
                )
            else:
                label = f"{color.name}  ·  (sin posición)"
            self.inkwell_combo.addItem(label, userData=cid)

    # ----------------------------------------------------------
    # Worker
    # ----------------------------------------------------------
    def _start_worker(self):
        self._worker = ManualControlWorker(self._controller)
        self._worker_thread = QThread()
        self._worker.moveToThread(self._worker_thread)

        self._worker.position_changed.connect(self.on_position_changed)
        self._worker.pen_state_changed.connect(self.on_pen_state_changed)
        self._worker.connection_changed.connect(self.on_connection_changed)
        self._worker.error.connect(self.on_worker_error)
        self._worker_thread.started.connect(self._worker.run)
        self._worker_thread.start()

    # ----------------------------------------------------------
    # Slots de comandos
    # ----------------------------------------------------------
    def _jog(self, sign_x: int, sign_y: int):
        if not self._connected:
            return
        step_in = mm_to_inches(self._jog_step_mm)
        self._worker.jog(sign_x * step_in, sign_y * step_in)

    def _set_jog_step(self, step_mm: float):
        self._jog_step_mm = step_mm

    @Slot()
    def on_go_to_coords(self):
        if not self._connected:
            return
        self._worker.go_to(
            mm_to_inches(self.goto_x.value()), mm_to_inches(self.goto_y.value())
        )

    @Slot()
    def on_home(self):
        if not self._connected:
            return
        self._worker.home()

    @Slot()
    def on_go_to_inkwell(self):
        if not self._connected or not self._session:
            return
        cid = self.inkwell_combo.currentData()
        if not cid:
            return
        color = self._session.colors.get(cid)
        if not color or not color.is_calibrated:
            QMessageBox.warning(
                self, "Sin posición", f"El tintero '{color.name}' no tiene posición."
            )
            return
        self._worker.go_to(color.inkwell_position.x, color.inkwell_position.y)

    @Slot()
    def on_dip_test(self):
        if not self._connected or not self._session:
            return
        cid = self.inkwell_combo.currentData()
        if not cid:
            return
        color = self._session.colors.get(cid)
        if not color or not color.is_calibrated:
            QMessageBox.warning(
                self, "Sin posición", f"El tintero '{color.name}' no tiene posición."
            )
            return
        ret = QMessageBox.question(
            self,
            "Probar recarga",
            f"Se ejecutará el ritual completo de recarga sobre '{color.name}'.\n\n"
            "Asegúrate de que el portaherramientas NO tiene pincel cargado, "
            "o de que el pincel está levantado.\n\n¿Continuar?",
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        self._worker.dip_test(color.inkwell_position)

    @Slot()
    def on_pen_up(self):
        if self._connected:
            self._worker.pen_up()

    @Slot()
    def on_pen_down(self):
        if self._connected:
            self._worker.pen_down()

    @Slot()
    def on_motors_off(self):
        if self._connected:
            self._worker.motors_off()

    @Slot()
    def on_motors_on(self):
        if self._connected:
            self._worker.motors_on()

    # ----------------------------------------------------------
    # Señales del worker
    # ----------------------------------------------------------
    @Slot(float, float)
    def on_position_changed(self, x: float, y: float):
        self._position = Point(x, y)
        x_mm = inches_to_mm(x)
        y_mm = inches_to_mm(y)
        self.pos_label.setText(
            f"X: {x_mm:7.1f} mm     Y: {y_mm:7.1f} mm"
        )

    @Slot(bool)
    def on_pen_state_changed(self, down: bool):
        self._pen_down = down

    @Slot(bool)
    def on_connection_changed(self, connected: bool):
        self._connected = connected
        if connected:
            self.status_dot.setStyleSheet("color: #639922; font-size: 14px;")
            self.status_label.setText("Plotter conectado")
        else:
            self.status_dot.setStyleSheet("color: #aaa; font-size: 14px;")
            self.status_label.setText("Desconectado")

    @Slot(str)
    def on_worker_error(self, msg: str):
        QMessageBox.critical(self, "Error de plotter", msg)

    # ----------------------------------------------------------
    # Captura de teclado para jog con flechas
    # ----------------------------------------------------------
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Left:
            self._jog(-1, 0)
            event.accept()
        elif event.key() == Qt.Key.Key_Right:
            self._jog(1, 0)
            event.accept()
        elif event.key() == Qt.Key.Key_Up:
            self._jog(0, -1)
            event.accept()
        elif event.key() == Qt.Key.Key_Down:
            self._jog(0, 1)
            event.accept()
        elif event.key() == Qt.Key.Key_Home:
            self.on_home()
            event.accept()
        else:
            super().keyPressEvent(event)

    # ----------------------------------------------------------
    # Cierre limpio
    # ----------------------------------------------------------
    def closeEvent(self, event):
        try:
            self._worker.shutdown()
            self._worker_thread.quit()
            self._worker_thread.wait(2000)
        except Exception:
            pass
        super().closeEvent(event)
