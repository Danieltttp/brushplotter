"""Lógica de layout del dibujo dentro de la cama del plotter.

Responsabilidad única: dadas las dimensiones originales del SVG, la
cama del plotter, una escala y un modo de posicionamiento, calcular:
- Si el dibujo cabe en la cama
- Qué tamaño físico resultante tendrá
- Dónde se posicionará (start_x, start_y)
- Cuánto margen sobra o cuánto excede

Sin dependencias de Qt. Testeable.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .units import cm_to_inches, inches_to_cm


class FitStatus(Enum):
    """Estado del encaje del dibujo en la cama."""
    OK = "ok"                # Cabe con margen cómodo (>1 cm)
    TIGHT = "tight"          # Cabe pero queda <1 cm de margen
    OVERFLOW = "overflow"    # No cabe


@dataclass
class LayoutResult:
    """Resultado de aplicar un layout. Todas las unidades en pulgadas
    (sistema interno). Para mostrar, los conversores de units.py.

    fits es True salvo en OVERFLOW.
    """
    status: FitStatus
    width_inches: float           # Ancho físico del dibujo escalado
    height_inches: float          # Alto físico del dibujo escalado
    start_x_inches: float         # Posición X de la esquina sup. izq.
    start_y_inches: float         # Posición Y de la esquina sup. izq.
    margin_x_inches: float        # Margen libre en X (negativo si excede)
    margin_y_inches: float        # Margen libre en Y (negativo si excede)
    scale_used: float             # Escala finalmente aplicada (1.0 = 100%)
    overflow_x_inches: float = 0  # Cuánto excede en X (0 si cabe)
    overflow_y_inches: float = 0  # Cuánto excede en Y (0 si cabe)

    @property
    def fits(self) -> bool:
        return self.status != FitStatus.OVERFLOW

    @property
    def message_short(self) -> str:
        """Mensaje corto para mostrar en la UI."""
        if self.status == FitStatus.OK:
            return "Cabe en la cama"
        if self.status == FitStatus.TIGHT:
            return "Cabe justo"
        # OVERFLOW
        ox = inches_to_cm(self.overflow_x_inches)
        oy = inches_to_cm(self.overflow_y_inches)
        if ox > 0 and oy > 0:
            return f"No cabe: excede {ox:.1f} × {oy:.1f} cm"
        if ox > 0:
            return f"No cabe: excede {ox:.1f} cm en ancho"
        return f"No cabe: excede {oy:.1f} cm en alto"


def compute_layout(
    svg_width_inches: float,
    svg_height_inches: float,
    bed_width_inches: float,
    bed_height_inches: float,
    scale: float = 1.0,
    centered: bool = True,
    manual_start_x_inches: float = 0.0,
    manual_start_y_inches: float = 0.0,
    tight_margin_cm: float = 1.0,
) -> LayoutResult:
    """Calcula el layout dado un SVG y una cama.

    Args:
        svg_width_inches/height: dimensiones originales del SVG.
        bed_width_inches/height: dimensiones de la cama del plotter
          (ya con orientación aplicada).
        scale: factor multiplicativo (1.0 = tamaño original; 0.5 = mitad).
        centered: si True, centra automáticamente; si False, usa
          manual_start_x/y.
        manual_start_x/y_inches: posición fija si centered=False.
        tight_margin_cm: umbral para considerar "cabe justo" en cm.

    Returns:
        LayoutResult con todos los datos calculados.
    """
    # Tamaño físico tras escala
    width = svg_width_inches * scale
    height = svg_height_inches * scale

    # Posición
    if centered:
        start_x = max(0.0, (bed_width_inches - width) / 2.0)
        start_y = max(0.0, (bed_height_inches - height) / 2.0)
    else:
        start_x = manual_start_x_inches
        start_y = manual_start_y_inches

    # Márgenes (positivos = espacio libre; negativos = excede)
    end_x = start_x + width
    end_y = start_y + height
    margin_x = bed_width_inches - end_x
    margin_y = bed_height_inches - end_y

    overflow_x = max(0.0, -margin_x)
    overflow_y = max(0.0, -margin_y)

    # Estado de encaje
    tight_threshold_inches = cm_to_inches(tight_margin_cm)
    if overflow_x > 0 or overflow_y > 0:
        status = FitStatus.OVERFLOW
    elif (
        margin_x < tight_threshold_inches
        or margin_y < tight_threshold_inches
    ):
        status = FitStatus.TIGHT
    else:
        status = FitStatus.OK

    return LayoutResult(
        status=status,
        width_inches=width,
        height_inches=height,
        start_x_inches=start_x,
        start_y_inches=start_y,
        margin_x_inches=margin_x,
        margin_y_inches=margin_y,
        scale_used=scale,
        overflow_x_inches=overflow_x,
        overflow_y_inches=overflow_y,
    )


def fit_to_bed_scale(
    svg_width_inches: float,
    svg_height_inches: float,
    bed_width_inches: float,
    bed_height_inches: float,
    margin_cm: float = 1.0,
) -> float:
    """Calcula la escala máxima que hace que el SVG quepa en la cama
    con cierto margen de seguridad alrededor.

    Devuelve un escalar entre 0 y N (puede ser > 1 si el SVG es muy
    pequeño respecto a la cama, queda a juicio del usuario aplicarlo).
    """
    if svg_width_inches <= 0 or svg_height_inches <= 0:
        return 1.0

    margin = cm_to_inches(margin_cm)
    available_w = bed_width_inches - 2 * margin
    available_h = bed_height_inches - 2 * margin

    if available_w <= 0 or available_h <= 0:
        return 1.0

    scale_w = available_w / svg_width_inches
    scale_h = available_h / svg_height_inches
    return min(scale_w, scale_h)
