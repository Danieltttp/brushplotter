"""Panel de configuración de la salida del dibujo en la cama.

Reúne todos los controles de v0.0.5:
- Tamaño/orientación de la cama (con catálogo de papeles)
- Escala (presets + slider + numérico)
- Indicador visual de encaje (cabe / cabe justo / no cabe)
- Centrado automático o posición manual

Emite señal layout_changed cada vez que algo cambia, para que la ventana
principal reaplique el layout sobre el PaintingSession y refresque el
preview.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..core.canvas_layout import (
    FitStatus,
    LayoutResult,
    compute_layout,
    fit_to_bed_scale,
)
from ..core.stroke_model import PaintingSession
from ..core.units import cm_to_inches, inches_to_cm
from ..hardware.paper_sizes import PAPER_SIZES, Orientation
from ..hardware.plotter_models import PLOTTER_MODELS


# Mapeo de modelo de plotter a tamaño de papel sugerido
PLOTTER_TO_PAPER = {
    "nextdraw_8511": "a4",
    "nextdraw_1117": "a3",
    "nextdraw_2234": "a1",
    "axidraw_v3": "letter",
    "axidraw_v3_xlx": "tabloid",
    "axidraw_a3": "a3",
}


# Estilos del indicador de encaje
INDICATOR_STYLES = {
    FitStatus.OK: {
        "bg": "#e6f4ea",
        "border": "#34a853",
        "text": "#0d652d",
        "icon": "✓",
    },
    FitStatus.TIGHT: {
        "bg": "#fef7e0",
        "border": "#f9ab00",
        "text": "#5f4500",
        "icon": "⚠",
    },
    FitStatus.OVERFLOW: {
        "bg": "#fce8e6",
        "border": "#ea4335",
        "text": "#a50e0e",
        "icon": "✕",
    },
}


class OutputConfigPanel(QWidget):
    """Panel completo de configuración de salida."""

    # Emitida cada vez que cualquier control cambia. La ventana principal
    # debe escuchar y aplicar el layout al PaintingSession activo.
    layout_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._session: PaintingSession | None = None
        self._updating = False  # guard para evitar bucles de señales

        self._build_ui()
        self._connect_signals()

    # ----------------------------------------------------------
    # Construcción
    # ----------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # SVG ORIGINAL
        layout.addWidget(self._section_label("SVG original"))
        self.svg_size_label = QLabel("— sin SVG —")
        self.svg_size_label.setStyleSheet(
            "font-family: 'Menlo', monospace; font-size: 12px; color: #555; "
            "padding: 4px 0;"
        )
        layout.addWidget(self.svg_size_label)

        layout.addSpacing(4)

        # PLOTTER + ORIENTACIÓN
        layout.addWidget(self._section_label("Cama del plotter"))
        self.plotter_combo = QComboBox()
        for key, model in PLOTTER_MODELS.items():
            self.plotter_combo.addItem(model.name, userData=key)
        layout.addWidget(self.plotter_combo)

        orient_row = QHBoxLayout()
        orient_row.setSpacing(4)
        self.btn_landscape = QPushButton("Apaisado")
        self.btn_portrait = QPushButton("Vertical")
        self.btn_landscape.setCheckable(True)
        self.btn_portrait.setCheckable(True)
        self.btn_landscape.setChecked(True)
        self._orient_group = QButtonGroup(self)
        self._orient_group.addButton(self.btn_landscape)
        self._orient_group.addButton(self.btn_portrait)
        self._orient_group.setExclusive(True)
        orient_row.addWidget(self.btn_landscape)
        orient_row.addWidget(self.btn_portrait)
        layout.addLayout(orient_row)

        self.bed_size_label = QLabel("")
        self.bed_size_label.setStyleSheet(
            "font-family: 'Menlo', monospace; font-size: 11px; color: #888; "
            "padding: 2px 0;"
        )
        layout.addWidget(self.bed_size_label)

        layout.addSpacing(4)

        # ESCALA
        layout.addWidget(self._section_label("Escala"))

        presets_row = QHBoxLayout()
        presets_row.setSpacing(4)
        self.preset_buttons: dict[str, QPushButton] = {}
        for label, value in [("25%", 0.25), ("50%", 0.50), ("100%", 1.0), ("Ajustar", -1)]:
            btn = QPushButton(label)
            btn.setStyleSheet("font-size: 11px; padding: 4px;")
            btn.clicked.connect(lambda _, v=value: self._apply_preset_scale(v))
            self.preset_buttons[label] = btn
            presets_row.addWidget(btn)
        layout.addLayout(presets_row)

        scale_row = QHBoxLayout()
        self.scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setRange(1, 400)  # 1% a 400%
        self.scale_slider.setValue(100)
        scale_row.addWidget(self.scale_slider)
        self.scale_spin = QSpinBox()
        self.scale_spin.setRange(1, 400)
        self.scale_spin.setValue(100)
        self.scale_spin.setSuffix(" %")
        self.scale_spin.setFixedWidth(72)
        scale_row.addWidget(self.scale_spin)
        layout.addLayout(scale_row)

        layout.addSpacing(4)

        # INDICADOR DE ENCAJE
        self.fit_indicator = self._build_fit_indicator()
        layout.addWidget(self.fit_indicator)

        layout.addSpacing(4)

        # POSICIÓN
        layout.addWidget(self._section_label("Posición"))
        self.center_check = QCheckBox("Centrar en la cama")
        self.center_check.setChecked(True)
        layout.addWidget(self.center_check)

        pos_grid = QGridLayout()
        pos_grid.setHorizontalSpacing(8)
        pos_grid.addWidget(QLabel("X"), 0, 0)
        self.pos_x_spin = QDoubleSpinBox()
        self.pos_x_spin.setRange(0, 1000)
        self.pos_x_spin.setSuffix(" cm")
        self.pos_x_spin.setDecimals(1)
        self.pos_x_spin.setEnabled(False)
        pos_grid.addWidget(self.pos_x_spin, 0, 1)
        pos_grid.addWidget(QLabel("Y"), 0, 2)
        self.pos_y_spin = QDoubleSpinBox()
        self.pos_y_spin.setRange(0, 1000)
        self.pos_y_spin.setSuffix(" cm")
        self.pos_y_spin.setDecimals(1)
        self.pos_y_spin.setEnabled(False)
        pos_grid.addWidget(self.pos_y_spin, 0, 3)
        layout.addLayout(pos_grid)

    def _build_fit_indicator(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("fitIndicator")
        self.fit_indicator = frame  # asignar antes de _apply_indicator_style
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)
        self.fit_icon = QLabel("✓")
        self.fit_icon.setStyleSheet("font-size: 16px;")
        layout.addWidget(self.fit_icon)
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self.fit_message = QLabel("Carga un SVG")
        self.fit_message.setStyleSheet("font-size: 12px; font-weight: 500;")
        text_col.addWidget(self.fit_message)
        self.fit_detail = QLabel("")
        self.fit_detail.setStyleSheet(
            "font-size: 11px; font-family: 'Menlo', monospace;"
        )
        text_col.addWidget(self.fit_detail)
        layout.addLayout(text_col, stretch=1)
        self._apply_indicator_style(FitStatus.OK)
        return frame

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            "font-size: 10px; color: #999; letter-spacing: 0.05em; "
            "margin-top: 4px;"
        )
        return lbl

    def _apply_indicator_style(self, status: FitStatus):
        s = INDICATOR_STYLES[status]
        self.fit_indicator.setStyleSheet(
            f"#fitIndicator {{ "
            f"background: {s['bg']}; "
            f"border: 1px solid {s['border']}; "
            f"border-radius: 4px; "
            f"}}"
        )
        self.fit_icon.setText(s["icon"])
        self.fit_icon.setStyleSheet(f"font-size: 16px; color: {s['text']};")
        self.fit_message.setStyleSheet(
            f"font-size: 12px; font-weight: 500; color: {s['text']};"
        )
        self.fit_detail.setStyleSheet(
            f"font-size: 11px; font-family: 'Menlo', monospace; color: {s['text']};"
        )

    # ----------------------------------------------------------
    # Conexión de señales
    # ----------------------------------------------------------
    def _connect_signals(self):
        self.plotter_combo.currentIndexChanged.connect(self._on_plotter_changed)
        self.btn_landscape.toggled.connect(self._on_orientation_changed)
        self.btn_portrait.toggled.connect(self._on_orientation_changed)
        self.scale_slider.valueChanged.connect(self._on_scale_slider)
        self.scale_spin.valueChanged.connect(self._on_scale_spin)
        self.center_check.toggled.connect(self._on_center_toggled)
        self.pos_x_spin.valueChanged.connect(self._recompute_and_emit)
        self.pos_y_spin.valueChanged.connect(self._recompute_and_emit)

    # ----------------------------------------------------------
    # API pública
    # ----------------------------------------------------------
    def set_session(self, session: PaintingSession | None):
        """Conecta el panel a una sesión. Refresca todos los controles
        a partir del estado actual de la sesión.
        """
        self._session = session
        self._updating = True

        if session is None:
            self.svg_size_label.setText("— sin SVG —")
            self.fit_message.setText("Carga un SVG")
            self.fit_detail.setText("")
            self._updating = False
            return

        # Mostrar tamaño nativo del SVG
        w_cm = inches_to_cm(session.svg_native_width_inches)
        h_cm = inches_to_cm(session.svg_native_height_inches)
        self.svg_size_label.setText(f"{w_cm:.1f} × {h_cm:.1f} cm")

        # Sincronizar plotter seleccionado
        for i in range(self.plotter_combo.count()):
            if self.plotter_combo.itemData(i) == self._guess_plotter_key():
                self.plotter_combo.setCurrentIndex(i)
                break

        self._update_bed_size_label()
        self._updating = False
        self._recompute_and_emit()

    def get_current_layout(self) -> LayoutResult | None:
        if self._session is None:
            return None
        return self._compute_layout()

    # ----------------------------------------------------------
    # Slots internos
    # ----------------------------------------------------------
    def _on_plotter_changed(self):
        if self._updating:
            return
        # Cambiar al papel sugerido para ese plotter
        plotter_key = self.plotter_combo.currentData()
        self._update_bed_size_label()
        self._recompute_and_emit()

    def _on_orientation_changed(self):
        if self._updating:
            return
        self._update_bed_size_label()
        self._recompute_and_emit()

    def _on_scale_slider(self, value: int):
        if self._updating:
            return
        self._updating = True
        self.scale_spin.setValue(value)
        self._updating = False
        self._recompute_and_emit()

    def _on_scale_spin(self, value: int):
        if self._updating:
            return
        self._updating = True
        self.scale_slider.setValue(value)
        self._updating = False
        self._recompute_and_emit()

    def _on_center_toggled(self, checked: bool):
        self.pos_x_spin.setEnabled(not checked)
        self.pos_y_spin.setEnabled(not checked)
        if not self._updating:
            self._recompute_and_emit()

    def _apply_preset_scale(self, value: float):
        if self._session is None:
            return
        if value < 0:
            # "Ajustar" — calcula la escala óptima
            bed_w, bed_h = self._current_bed_dimensions_inches()
            s = fit_to_bed_scale(
                self._session.svg_native_width_inches,
                self._session.svg_native_height_inches,
                bed_w,
                bed_h,
                margin_cm=1.0,
            )
            pct = int(round(s * 100))
        else:
            pct = int(round(value * 100))
        pct = max(1, min(400, pct))
        self._updating = True
        self.scale_slider.setValue(pct)
        self.scale_spin.setValue(pct)
        self._updating = False
        self._recompute_and_emit()

    # ----------------------------------------------------------
    # Cálculos
    # ----------------------------------------------------------
    def _current_bed_dimensions_inches(self) -> tuple[float, float]:
        """Devuelve (ancho, alto) en pulgadas SIEMPRE en orientación
        física del plotter (X = lado largo).

        La cama del plotter no rota: tiene una orientación física fija.
        Lo que rota es el dibujo dentro de ella (ver _current_rotation).
        """
        from ..hardware.plotter_models import get_model
        key = self.plotter_combo.currentData()
        if not key:
            return (34.02, 23.39)
        model = get_model(key)
        return (model.max_x_inches, model.max_y_inches)

    def _current_rotation(self) -> int:
        """Devuelve la rotación a aplicar al dibujo (0 o 90)."""
        return 90 if self.btn_portrait.isChecked() else 0

    def _current_drawing_dimensions_inches(self) -> tuple[float, float]:
        """Dimensiones físicas del dibujo después de escala y rotación."""
        if self._session is None:
            return (0.0, 0.0)
        scale = self.scale_spin.value() / 100.0
        w = self._session.svg_native_width_inches * scale
        h = self._session.svg_native_height_inches * scale
        if self._current_rotation() == 90:
            return (h, w)
        return (w, h)

    def _update_bed_size_label(self):
        bw, bh = self._current_bed_dimensions_inches()
        self.bed_size_label.setText(
            f"{inches_to_cm(bw):.1f} × {inches_to_cm(bh):.1f} cm"
        )

    def _guess_plotter_key(self) -> str:
        if self._session is None:
            return "nextdraw_2234"
        # Mantener el actual si la sesión ya tiene una cama configurada
        for key, model in PLOTTER_MODELS.items():
            if abs(model.max_x_inches - self._session.canvas.plotter_max_x) < 0.1:
                return key
        return "nextdraw_2234"

    def _compute_layout(self) -> LayoutResult:
        assert self._session is not None
        bed_w, bed_h = self._current_bed_dimensions_inches()
        scale = self.scale_spin.value() / 100.0
        # Si está rotado 90°, las dimensiones del dibujo se intercambian
        if self._current_rotation() == 90:
            svg_w = self._session.svg_native_height_inches
            svg_h = self._session.svg_native_width_inches
        else:
            svg_w = self._session.svg_native_width_inches
            svg_h = self._session.svg_native_height_inches
        return compute_layout(
            svg_width_inches=svg_w,
            svg_height_inches=svg_h,
            bed_width_inches=bed_w,
            bed_height_inches=bed_h,
            scale=scale,
            centered=self.center_check.isChecked(),
            manual_start_x_inches=cm_to_inches(self.pos_x_spin.value()),
            manual_start_y_inches=cm_to_inches(self.pos_y_spin.value()),
        )

    def _recompute_and_emit(self):
        if self._session is None:
            return
        result = self._compute_layout()

        # Actualizar indicador
        self._apply_indicator_style(result.status)
        self.fit_message.setText(result.message_short)
        self.fit_detail.setText(
            f"Salida: {inches_to_cm(result.width_inches):.1f} × "
            f"{inches_to_cm(result.height_inches):.1f} cm"
        )

        # Si centrado, reflejar las coordenadas calculadas en los spinners
        if self.center_check.isChecked():
            self._updating = True
            self.pos_x_spin.setValue(inches_to_cm(result.start_x_inches))
            self.pos_y_spin.setValue(inches_to_cm(result.start_y_inches))
            self._updating = False

        # Aplicar al session
        bed_w, bed_h = self._current_bed_dimensions_inches()
        self._session.canvas.plotter_max_x = bed_w
        self._session.canvas.plotter_max_y = bed_h
        self._session.canvas.start_x = result.start_x_inches
        self._session.canvas.start_y = result.start_y_inches
        self._session.canvas.drawing_width = result.width_inches
        self._session.canvas.scale_factor = result.scale_used
        self._session.canvas.centered = self.center_check.isChecked()
        self._session.canvas.rotation_degrees = self._current_rotation()

        self.layout_changed.emit()
