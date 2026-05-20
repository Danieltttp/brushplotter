"""Conversión y formato de unidades, centralizado.

Internamente todo lo que toca al plotter usa pulgadas (unidad nativa
del SDK de NextDraw/AxiDraw). La interfaz usa centímetros, que es la
unidad natural para artistas trabajando con formatos de papel A0-A5.

Mantén las conversiones aquí. No las dispereses por la UI.
"""

from __future__ import annotations

# Constantes
INCH_TO_MM = 25.4
INCH_TO_CM = 2.54
MM_TO_INCH = 1.0 / INCH_TO_MM
CM_TO_INCH = 1.0 / INCH_TO_CM


# ---------- Pulgadas ↔ otras unidades ----------
def inches_to_mm(inches: float) -> float:
    return inches * INCH_TO_MM


def inches_to_cm(inches: float) -> float:
    return inches * INCH_TO_CM


def mm_to_inches(mm: float) -> float:
    return mm * MM_TO_INCH


def cm_to_inches(cm: float) -> float:
    return cm * CM_TO_INCH


# ---------- mm ↔ cm ----------
def mm_to_cm(mm: float) -> float:
    return mm / 10.0


def cm_to_mm(cm: float) -> float:
    return cm * 10.0


# ---------- Formato de presentación ----------
def format_cm(value_inches: float, decimals: int = 1) -> str:
    """Formatea un valor en pulgadas como 'XX.X cm'."""
    return f"{inches_to_cm(value_inches):.{decimals}f} cm"


def format_size_cm(width_inches: float, height_inches: float, decimals: int = 1) -> str:
    """Formatea un tamaño 2D como 'WW.W × HH.H cm'."""
    w = inches_to_cm(width_inches)
    h = inches_to_cm(height_inches)
    return f"{w:.{decimals}f} × {h:.{decimals}f} cm"


def format_mm(value_inches: float, decimals: int = 1) -> str:
    return f"{inches_to_mm(value_inches):.{decimals}f} mm"
