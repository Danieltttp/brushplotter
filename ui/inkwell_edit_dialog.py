"""Diálogo simple para editar un tintero (nombre + posición manual).

Solución temporal mientras no esté el diálogo de calibración interactivo
con jog del cabezal. Permite teclear coordenadas en mm directamente.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ..core.stroke_model import InkColor, Point, inches_to_mm, mm_to_inches


class InkwellEditDialog(QDialog):
    """Diálogo para editar un único tintero.

    Devuelve un nuevo InkColor (no muta el original) si se acepta.
    """

    def __init__(self, color: InkColor, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Editar tintero: {color.name}")
        self.setMinimumWidth(360)

        self._original_color = color
        self._hex = color.hex

        layout = QVBoxLayout(self)

        form = QFormLayout()

        # Nombre
        self.name_edit = QLineEdit(color.name)
        form.addRow("Nombre", self.name_edit)

        # Color (botón con muestra)
        color_row = QHBoxLayout()
        self.color_button = QPushButton(color.hex)
        self.color_button.clicked.connect(self._pick_color)
        self._update_color_button()
        color_row.addWidget(self.color_button)
        form.addRow("Color", color_row)

        # Coordenadas en mm
        if color.is_calibrated:
            x_mm = inches_to_mm(color.inkwell_position.x)
            y_mm = inches_to_mm(color.inkwell_position.y)
        else:
            x_mm = 25.4  # 1 pulgada por defecto
            y_mm = 25.4

        self.x_spin = QDoubleSpinBox()
        self.x_spin.setRange(0.0, 1000.0)
        self.x_spin.setSuffix(" mm")
        self.x_spin.setDecimals(1)
        self.x_spin.setValue(x_mm)
        form.addRow("Posición X", self.x_spin)

        self.y_spin = QDoubleSpinBox()
        self.y_spin.setRange(0.0, 1000.0)
        self.y_spin.setSuffix(" mm")
        self.y_spin.setDecimals(1)
        self.y_spin.setValue(y_mm)
        form.addRow("Posición Y", self.y_spin)

        layout.addLayout(form)

        # Botones
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _pick_color(self):
        col = QColorDialog.getColor(QColor(self._hex), self)
        if col.isValid():
            self._hex = col.name()
            self._update_color_button()

    def _update_color_button(self):
        self.color_button.setText(self._hex)
        palette = self.color_button.palette()
        palette.setColor(QPalette.ColorRole.Button, QColor(self._hex))
        self.color_button.setPalette(palette)
        self.color_button.setStyleSheet(
            f"background-color: {self._hex}; color: white; "
            f"padding: 6px; font-family: monospace;"
        )

    def build_color(self) -> InkColor:
        """Construye el InkColor resultante (llamar tras accept())."""
        return InkColor(
            name=self.name_edit.text(),
            hex=self._hex,
            inkwell_position=Point(
                mm_to_inches(self.x_spin.value()),
                mm_to_inches(self.y_spin.value()),
            ),
        )
