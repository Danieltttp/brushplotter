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


class InkwellPanel(QWidget):
    """Panel con la lista de tinteros."""

    edit_requested = Signal(str)
    goto_requested = Signal(str)
    add_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)

        title = QLabel("TINTEROS")
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
        """Reemplaza el contenido con los colores de la sesión."""
        # Limpiar items previos
        while self._items_container.count():
            item = self._items_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for cid, color in session.colors.items():
            row = InkwellItem(cid, color)
            row.edit_requested.connect(self.edit_requested.emit)
            row.goto_requested.connect(self.goto_requested.emit)
            self._items_container.addWidget(row)
