"""Catálogo de tamaños de papel estándar.

Series ISO (A0-A5), tamaños imperiales comunes (Carta, Tabloide) y
tamaños de plotter explícitos (que coinciden con A4/A3/A1 pero los
mantenemos para coherencia con el catálogo de plotter_models).

Todas las dimensiones en milímetros (versión vertical: width <= height).
La función rotate_to() facilita aplicar orientación.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Orientation(Enum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


@dataclass(frozen=True)
class PaperSize:
    """Tamaño de papel en milímetros (formato vertical por defecto)."""
    name: str
    width_mm: float   # lado corto (vertical)
    height_mm: float  # lado largo (vertical)

    def dimensions(self, orientation: Orientation) -> tuple[float, float]:
        """Devuelve (ancho, alto) en mm según orientación."""
        if orientation == Orientation.PORTRAIT:
            return (self.width_mm, self.height_mm)
        return (self.height_mm, self.width_mm)

    @property
    def width_cm(self) -> float:
        return self.width_mm / 10.0

    @property
    def height_cm(self) -> float:
        return self.height_mm / 10.0


PAPER_SIZES: dict[str, PaperSize] = {
    # Serie ISO 216 — A
    "a0": PaperSize("A0", 841, 1189),
    "a1": PaperSize("A1", 594, 841),
    "a2": PaperSize("A2", 420, 594),
    "a3": PaperSize("A3", 297, 420),
    "a4": PaperSize("A4", 210, 297),
    "a5": PaperSize("A5", 148, 210),
    # Imperiales
    "letter": PaperSize("Carta", 215.9, 279.4),         # 8.5 × 11"
    "tabloid": PaperSize("Tabloide", 279.4, 431.8),     # 11 × 17"
    "legal": PaperSize("Legal", 215.9, 355.6),          # 8.5 × 14"
}


def get_paper(key: str) -> PaperSize:
    if key not in PAPER_SIZES:
        raise KeyError(
            f"Tamaño desconocido: {key}. Disponibles: {list(PAPER_SIZES.keys())}"
        )
    return PAPER_SIZES[key]
