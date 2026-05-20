"""Perfiles de modelos de plotter.

Cada modelo tiene distinta área útil. Centralizamos aquí para que el resto
del código no contenga magic numbers.

Fuentes oficiales:
- NextDraw 8511: 8.5 x 11" (A4)
- NextDraw 1117: 11 x 17" (A3)
- NextDraw 2234: 22 x 34" / 34.02 x 23.39" físicos (A1)
- AxiDraw V3: 11.81 x 8.58"
- AxiDraw V3 XLX: 17 x 11"
- AxiDraw SE/A3: 16.93 x 11.69"
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlotterModel:
    """Especificaciones físicas de un modelo de plotter."""
    name: str
    max_x_inches: float
    max_y_inches: float
    supports_auto_homing: bool
    sdk: str  # 'nextdraw' o 'axidraw'

    @property
    def max_x_mm(self) -> float:
        return self.max_x_inches * 25.4

    @property
    def max_y_mm(self) -> float:
        return self.max_y_inches * 25.4


PLOTTER_MODELS: dict[str, PlotterModel] = {
    "nextdraw_8511": PlotterModel(
        name="NextDraw 8511 (A4)",
        max_x_inches=11.0,
        max_y_inches=8.5,
        supports_auto_homing=True,
        sdk="nextdraw",
    ),
    "nextdraw_1117": PlotterModel(
        name="NextDraw 1117 (A3)",
        max_x_inches=17.0,
        max_y_inches=11.0,
        supports_auto_homing=True,
        sdk="nextdraw",
    ),
    "nextdraw_2234": PlotterModel(
        name="NextDraw 2234 (A1)",
        max_x_inches=34.02,
        max_y_inches=23.39,
        supports_auto_homing=True,
        sdk="nextdraw",
    ),
    "axidraw_v3": PlotterModel(
        name="AxiDraw V3",
        max_x_inches=11.81,
        max_y_inches=8.58,
        supports_auto_homing=False,
        sdk="axidraw",
    ),
    "axidraw_v3_xlx": PlotterModel(
        name="AxiDraw V3 XLX",
        max_x_inches=17.0,
        max_y_inches=11.0,
        supports_auto_homing=False,
        sdk="axidraw",
    ),
    "axidraw_a3": PlotterModel(
        name="AxiDraw SE/A3",
        max_x_inches=16.93,
        max_y_inches=11.69,
        supports_auto_homing=False,
        sdk="axidraw",
    ),
}


DEFAULT_MODEL_KEY = "nextdraw_2234"


def get_model(key: str) -> PlotterModel:
    if key not in PLOTTER_MODELS:
        raise KeyError(
            f"Modelo desconocido: {key}. Disponibles: {list(PLOTTER_MODELS.keys())}"
        )
    return PLOTTER_MODELS[key]
