"""Diálogo simple para editar la posición de la estación de agua.

Similar al de tinteros pero solo con coordenadas (no hay color que
configurar — el agua es agua).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from ..core.stroke_model import Point, WaterStation
from ..core.units import cm_to_inches, inches_to_cm


class WaterStationEditDialog(QDialog):
    """Diálogo para editar la posición de la estación de agua."""

    def __init__(self, water: WaterStation, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Estación de agua")
        self.setMinimumWidth(340)

        layout = QVBoxLayout(self)

        # Explicación corta
        info = QLabel(
            "Posición física donde el pincel pasa por agua para limpiarse "
            "o humedecerse antes de cargar pintura. Útil para acuarela."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; font-size: 11px; padding-bottom: 8px;")
        layout.addWidget(info)

        form = QFormLayout()

        if water.is_calibrated:
            x_cm = inches_to_cm(water.position.x)
            y_cm = inches_to_cm(water.position.y)
        else:
            x_cm = 2.0  # 2 cm por defecto, cerca del Home
            y_cm = 2.0

        self.x_spin = QDoubleSpinBox()
        self.x_spin.setRange(0.0, 100.0)
        self.x_spin.setSuffix(" cm")
        self.x_spin.setDecimals(1)
        self.x_spin.setValue(x_cm)
        form.addRow("Posición X", self.x_spin)

        self.y_spin = QDoubleSpinBox()
        self.y_spin.setRange(0.0, 100.0)
        self.y_spin.setSuffix(" cm")
        self.y_spin.setDecimals(1)
        self.y_spin.setValue(y_cm)
        form.addRow("Posición Y", self.y_spin)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def build_water_station(self) -> WaterStation:
        """Construye el WaterStation resultante."""
        return WaterStation(
            position=Point(
                cm_to_inches(self.x_spin.value()),
                cm_to_inches(self.y_spin.value()),
            ),
            name="Agua",
        )
