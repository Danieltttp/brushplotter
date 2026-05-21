"""Widget reutilizable: panel de tinteros (colores + posiciones).

Usado tanto en la ventana principal (vista de solo lectura, con
indicador de "sin posición") como dentro del diálogo de calibración
(con edición completa).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..core.stroke_model import InkColor, PaintingSession, inches_to_mm


class ColorSwatch(QWidget):
    """Cuadradito de color (sustituye al ⬤ del mockup)."""

    def __init__(self, hex_color: str, size: int = 14, parent=None):
        super().__init__(parent)
        self._color = QColor(hex_color)
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(self._color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(self.rect())


class InkwellItem(QFrame):
    """Una fila de tintero en el panel."""

    edit_requested = Signal(str)  # emite color_id
    goto_requested = Signal(str)

    def __init__(self, color_id: str, color: InkColor, parent=None):
        super().__init__(parent)
        self._color_id = color_id
        self.setFrameStyle(QFrame.Shape.StyledPanel)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        swatch = ColorSwatch(color.hex)
        layout.addWidget(swatch)

        text_col = QVBoxLayout()
        text_col.setSpacing(0)
        name_label = QLabel(color.name)
        name_label.setStyleSheet("font-size: 12px; font-weight: 500;")
        text_col.addWidget(name_label)

        if color.is_calibrated:
            ink = color.inkwell_position
            coord = f"{inches_to_mm(ink.x):.1f}, {inches_to_mm(ink.y):.1f} mm"
            style = "font-size: 10px; color: #888; font-family: 'Menlo', 'Courier New', monospace;"
        else:
            coord = "sin posición"
            style = "font-size: 10px; color: #c47600; font-family: 'Menlo', 'Courier New', monospace;"
        coord_label = QLabel(coord)
        coord_label.setStyleSheet(style)
        text_col.addWidget(coord_label)
        layout.addLayout(text_col, stretch=1)

        if color.is_calibrated:
            btn_goto = QPushButton("⌖")
            btn_goto.setFixedSize(24, 24)
            btn_goto.setToolTip("Ir a esta posición")
            btn_goto.clicked.connect(
                lambda: self.goto_requested.emit(self._color_id)
            )
            layout.addWidget(btn_goto)

        btn_edit = QPushButton("✎")
        btn_edit.setFixedSize(24, 24)
        btn_edit.setToolTip("Editar")
        btn_edit.clicked.connect(
            lambda: self.edit_requested.emit(self._color_id)
        )
        layout.addWidget(btn_edit)


class WaterStationItem(QFrame):
    """Fila especial para la estación de agua (compartida).

    Layout (v0.0.6.4): el botón de configurar se mueve a una fila propia
    en lugar de competir por espacio en la cabecera. Garantiza
    visibilidad incluso en sidebars muy estrechos.

        ┌─────────────────────────────────────────────┐
        │ 💧  Estación de agua                         │
        │     25.4, 25.4 mm  o  ⚠ sin posición        │
        │ ─────────────────────────────────────────── │
        │ [✓] Antes de recargar (rápido)              │
        │ [✓] Al cambiar de color (profundo)          │
        │ ─────────────────────────────────────────── │
        │  [⌖ Ir]   [✎ Configurar posición]           │
        └─────────────────────────────────────────────┘
    """

    edit_requested = Signal()
    goto_requested = Signal()
    toggle_before_dip = Signal(bool)
    toggle_on_color_change = Signal(bool)

    def __init__(
        self,
        water,
        before_dip_enabled: bool,
        on_color_change_enabled: bool,
        parent=None,
    ):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "WaterStationItem { border: 1px solid #5b9bd5; "
            "border-radius: 4px; background: #f0f6fb; }"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(6)

        # ── Fila 1: icono + nombre + coordenadas ──
        top = QHBoxLayout()
        top.setSpacing(8)

        icon = QLabel("💧")
        icon.setStyleSheet("font-size: 14px;")
        top.addWidget(icon)

        text_col = QVBoxLayout()
        text_col.setSpacing(0)
        name_label = QLabel("Estación de agua")
        name_label.setStyleSheet("font-size: 12px; font-weight: 500; color: #234;")
        text_col.addWidget(name_label)

        if water.is_calibrated:
            from ..core.units import inches_to_mm
            coord = (
                f"{inches_to_mm(water.position.x):.1f}, "
                f"{inches_to_mm(water.position.y):.1f} mm"
            )
            style = (
                "font-size: 10px; color: #5b9bd5; "
                "font-family: 'Menlo', 'Courier New', monospace;"
            )
        else:
            coord = "⚠ sin posición"
            style = (
                "font-size: 10px; color: #c47600; "
                "font-family: 'Menlo', 'Courier New', monospace;"
            )
        coord_label = QLabel(coord)
        coord_label.setStyleSheet(style)
        text_col.addWidget(coord_label)
        top.addLayout(text_col, stretch=1)

        outer.addLayout(top)

        # ── Fila 2+: checkboxes ──
        from PySide6.QtWidgets import QCheckBox
        self.check_before = QCheckBox("Antes de recargar (rápido)")
        self.check_before.setChecked(before_dip_enabled)
        self.check_before.setToolTip(
            "Pasa por agua brevemente antes de cargar el mismo color. "
            "Útil para mantener humedad y eliminar restos secos."
        )
        self.check_before.setStyleSheet("font-size: 11px; color: #234;")
        self.check_before.toggled.connect(self.toggle_before_dip.emit)
        outer.addWidget(self.check_before)

        self.check_change = QCheckBox("Al cambiar de color (profundo)")
        self.check_change.setChecked(on_color_change_enabled)
        self.check_change.setToolTip(
            "Limpieza profunda con secado al aire cuando se cambia de un "
            "color a otro. Evita contaminar el siguiente tintero."
        )
        self.check_change.setStyleSheet("font-size: 11px; color: #234;")
        self.check_change.toggled.connect(self.toggle_on_color_change.emit)
        outer.addWidget(self.check_change)

        # ── Fila final: botones de acción anchos ──
        # Los ponemos en fila propia para garantizar visibilidad
        # incluso en sidebars muy estrechos. Forzamos colores legibles
        # en modo claro y oscuro (el fondo del item es azul claro fijo,
        # así que el texto va siempre en azul oscuro).
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(6)

        # Estilo común para todos los botones del item de agua: fondo
        # blanco, texto azul oscuro, hover azul claro. Independiente
        # del tema del sistema.
        common_btn_style = (
            "QPushButton { "
            "  background-color: #ffffff; "
            "  color: #1a4a78; "
            "  border: 1px solid #5b9bd5; "
            "  border-radius: 4px; "
            "  padding: 5px 10px; "
            "  font-size: 11px; "
            "} "
            "QPushButton:hover { background-color: #e6f0fa; } "
            "QPushButton:pressed { background-color: #d4e6f7; } "
        )

        if water.is_calibrated:
            btn_goto = QPushButton("⌖ Ir")
            btn_goto.setToolTip("Mover el cabezal a la estación de agua")
            btn_goto.setStyleSheet(common_btn_style)
            btn_goto.clicked.connect(self.goto_requested.emit)
            buttons_row.addWidget(btn_goto)

        # Botón de configurar/editar SIEMPRE visible. Cuando no está
        # calibrada, fondo amarillo de aviso para llamar la atención.
        if water.is_calibrated:
            btn_edit = QPushButton("✎ Editar posición")
            btn_edit.setStyleSheet(common_btn_style)
        else:
            btn_edit = QPushButton("✎ Configurar posición")
            btn_edit.setStyleSheet(
                "QPushButton { "
                "  background-color: #fff3cd; "
                "  color: #856404; "
                "  border: 1px solid #c47600; "
                "  border-radius: 4px; "
                "  padding: 5px 10px; "
                "  font-size: 11px; "
                "  font-weight: 500; "
                "} "
                "QPushButton:hover { background-color: #ffe9a3; } "
                "QPushButton:pressed { background-color: #ffd966; } "
            )
        btn_edit.clicked.connect(self.edit_requested.emit)
        buttons_row.addWidget(btn_edit, stretch=1)

        outer.addLayout(buttons_row)


class InkwellPanel(QWidget):
    """Panel con la lista de tinteros + estación de agua."""

    edit_requested = Signal(str)
    goto_requested = Signal(str)
    add_requested = Signal()
    edit_water_requested = Signal()
    goto_water_requested = Signal()
    toggle_water_before_dip = Signal(bool)
    toggle_water_on_color_change = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)

        title = QLabel("TINTEROS Y AGUA")
        title.setStyleSheet(
            "font-size: 11px; color: #999; letter-spacing: 0.05em;"
        )
        self._layout.addWidget(title)

        self._items_container = QVBoxLayout()
        self._items_container.setSpacing(4)
        self._layout.addLayout(self._items_container)

        self._add_btn = QPushButton("+ Añadir tintero")
        self._add_btn.clicked.connect(self.add_requested.emit)
        self._layout.addWidget(self._add_btn)

        self._layout.addStretch()

    def set_session(self, session: PaintingSession):
        """Reemplaza el contenido con los colores + agua de la sesión."""
        while self._items_container.count():
            item = self._items_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        water_item = WaterStationItem(
            session.water_station,
            before_dip_enabled=session.material_profile.uses_water_before_dip,
            on_color_change_enabled=session.material_profile.uses_water_on_color_change,
        )
        water_item.edit_requested.connect(self.edit_water_requested.emit)
        water_item.goto_requested.connect(self.goto_water_requested.emit)
        water_item.toggle_before_dip.connect(self.toggle_water_before_dip.emit)
        water_item.toggle_on_color_change.connect(self.toggle_water_on_color_change.emit)
        self._items_container.addWidget(water_item)

        for cid, color in session.colors.items():
            row = InkwellItem(cid, color)
            row.edit_requested.connect(self.edit_requested.emit)
            row.goto_requested.connect(self.goto_requested.emit)
            self._items_container.addWidget(row)
