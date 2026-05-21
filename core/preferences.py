"""Preferencias persistentes de brushplotter.

Wrapper limpio sobre QSettings para que el resto del código no tenga
que conocer las claves ni las conversiones.

En macOS, QSettings escribe en:
  ~/Library/Preferences/com.danielgarciaandujar.brushplotter.plist

En Linux:
  ~/.config/Daniel García Andújar/brushplotter.conf

En Windows: en el registro, bajo HKEY_CURRENT_USER/Software/...

Diseño:
- Una sola instancia (singleton via get_preferences()).
- Todas las posiciones se guardan en PULGADAS (unidad interna).
- Tinteros/agua son GLOBALES: una sola entrada para cada uno,
  identificada por su nombre. No depende del SVG cargado.
- Si una preferencia no existe, los getters devuelven un default
  razonable; nunca lanzan excepción.
"""

from __future__ import annotations

import json
from typing import Optional

from PySide6.QtCore import QByteArray, QSettings

from .stroke_model import (
    DEFAULT_PROFILES,
    InkColor,
    MaterialProfile,
    Point,
    WaterStation,
)


# Claves bajo el namespace de la app
class K:
    # Hardware / sesión por defecto
    PLOTTER_MODEL = "hardware/plotter_model"
    MATERIAL_KEY = "session/material_key"
    SPEED_PENDOWN = "session/speed_pendown"
    RECHARGE_CM = "session/recharge_cm"
    USES_WATER_BEFORE_DIP = "session/uses_water_before_dip"
    USES_WATER_ON_COLOR_CHANGE = "session/uses_water_on_color_change"

    # Posiciones físicas (en pulgadas, JSON)
    INKWELLS_JSON = "calibration/inkwells_json"
    WATER_STATION_JSON = "calibration/water_station_json"

    # Geometría de ventana
    WINDOW_GEOMETRY = "ui/window_geometry"
    WINDOW_STATE = "ui/window_state"

    # Diálogos
    LAST_SVG_DIR = "ui/last_svg_dir"


class Preferences:
    """Wrapper tipado sobre QSettings."""

    def __init__(self):
        # Application/Organization están configurados en __main__.py
        self._s = QSettings()

    # ----- Hardware / sesión -----
    def get_plotter_model(self, default: str = "nextdraw_2234") -> str:
        return self._s.value(K.PLOTTER_MODEL, default, type=str)

    def set_plotter_model(self, key: str) -> None:
        self._s.setValue(K.PLOTTER_MODEL, key)

    def get_material_key(self, default: str = "acuarela") -> str:
        return self._s.value(K.MATERIAL_KEY, default, type=str)

    def set_material_key(self, key: str) -> None:
        self._s.setValue(K.MATERIAL_KEY, key)

    def get_speed_pendown(self, default: int = 5) -> int:
        # QSettings devuelve strings en algunos backends; forzamos int.
        try:
            return int(self._s.value(K.SPEED_PENDOWN, default))
        except (TypeError, ValueError):
            return default

    def set_speed_pendown(self, value: int) -> None:
        self._s.setValue(K.SPEED_PENDOWN, int(value))

    def get_recharge_cm(self, default: float = 12.7) -> float:
        try:
            return float(self._s.value(K.RECHARGE_CM, default))
        except (TypeError, ValueError):
            return default

    def set_recharge_cm(self, value: float) -> None:
        self._s.setValue(K.RECHARGE_CM, float(value))

    def get_uses_water_before_dip(self, default: bool = True) -> bool:
        return self._read_bool(K.USES_WATER_BEFORE_DIP, default)

    def set_uses_water_before_dip(self, value: bool) -> None:
        self._s.setValue(K.USES_WATER_BEFORE_DIP, bool(value))

    def get_uses_water_on_color_change(self, default: bool = True) -> bool:
        return self._read_bool(K.USES_WATER_ON_COLOR_CHANGE, default)

    def set_uses_water_on_color_change(self, value: bool) -> None:
        self._s.setValue(K.USES_WATER_ON_COLOR_CHANGE, bool(value))

    # ----- Calibración (globales por nombre) -----
    def get_inkwells(self) -> dict[str, dict]:
        """Devuelve un dict {name: {"x": pulgadas, "y": pulgadas, "hex": str}}.

        Es global, no depende del SVG cargado.
        """
        raw = self._s.value(K.INKWELLS_JSON, "")
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, TypeError):
            pass
        return {}

    def set_inkwells(self, inkwells: dict[str, dict]) -> None:
        self._s.setValue(K.INKWELLS_JSON, json.dumps(inkwells))

    def upsert_inkwell(self, name: str, color: InkColor) -> None:
        """Añade o actualiza un tintero global por su nombre."""
        if not color.is_calibrated:
            return
        inkwells = self.get_inkwells()
        inkwells[name] = {
            "x": color.inkwell_position.x,
            "y": color.inkwell_position.y,
            "hex": color.hex,
        }
        self.set_inkwells(inkwells)

    def get_water_station(self) -> Optional[Point]:
        raw = self._s.value(K.WATER_STATION_JSON, "")
        if not raw:
            return None
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and "x" in data and "y" in data:
                return Point(float(data["x"]), float(data["y"]))
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        return None

    def set_water_station(self, water: WaterStation) -> None:
        if not water.is_calibrated:
            self._s.remove(K.WATER_STATION_JSON)
            return
        self._s.setValue(
            K.WATER_STATION_JSON,
            json.dumps({"x": water.position.x, "y": water.position.y}),
        )

    # ----- Geometría de ventana -----
    def get_window_geometry(self) -> Optional[QByteArray]:
        v = self._s.value(K.WINDOW_GEOMETRY)
        if isinstance(v, QByteArray) and not v.isEmpty():
            return v
        return None

    def set_window_geometry(self, value: QByteArray) -> None:
        self._s.setValue(K.WINDOW_GEOMETRY, value)

    def get_window_state(self) -> Optional[QByteArray]:
        v = self._s.value(K.WINDOW_STATE)
        if isinstance(v, QByteArray) and not v.isEmpty():
            return v
        return None

    def set_window_state(self, value: QByteArray) -> None:
        self._s.setValue(K.WINDOW_STATE, value)

    # ----- Diálogos -----
    def get_last_svg_dir(self, default: str = "") -> str:
        return self._s.value(K.LAST_SVG_DIR, default, type=str)

    def set_last_svg_dir(self, path: str) -> None:
        self._s.setValue(K.LAST_SVG_DIR, path)

    # ----- Mantenimiento -----
    def reset_all(self) -> None:
        """Borra todas las preferencias. La próxima sesión arranca limpia."""
        self._s.clear()
        self._s.sync()

    def sync(self) -> None:
        """Fuerza escritura a disco (útil antes de cerrar la app)."""
        self._s.sync()

    # ----- Helpers privados -----
    def _read_bool(self, key: str, default: bool) -> bool:
        v = self._s.value(key, default)
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on")
        try:
            return bool(int(v))
        except (TypeError, ValueError):
            return default


# Singleton perezoso
_instance: Optional[Preferences] = None


def get_preferences() -> Preferences:
    global _instance
    if _instance is None:
        _instance = Preferences()
    return _instance


# ----- Funciones de aplicación a/desde sesión -----
def apply_calibration_to_session(session, prefs: Optional[Preferences] = None) -> int:
    """Recorre los colores de la sesión y, si hay calibración guardada
    para un color con el mismo nombre, le asigna la posición.

    Devuelve el número de colores que recibieron calibración.

    También aplica la estación de agua y los flags de uso de agua.
    """
    if prefs is None:
        prefs = get_preferences()

    count = 0
    stored = prefs.get_inkwells()
    for cid, color in session.colors.items():
        if color.name in stored:
            entry = stored[color.name]
            try:
                session.colors[cid] = InkColor(
                    name=color.name,
                    hex=entry.get("hex", color.hex),
                    inkwell_position=Point(float(entry["x"]), float(entry["y"])),
                )
                count += 1
            except (KeyError, ValueError, TypeError):
                continue

    # Estación de agua global
    water_pos = prefs.get_water_station()
    if water_pos is not None:
        session.water_station = WaterStation(position=water_pos, name="Agua")

    # Flags de agua (sobreescriben los del material si el usuario los
    # tocó en sesiones anteriores)
    session.material_profile.uses_water_before_dip = prefs.get_uses_water_before_dip(
        session.material_profile.uses_water_before_dip
    )
    session.material_profile.uses_water_on_color_change = (
        prefs.get_uses_water_on_color_change(
            session.material_profile.uses_water_on_color_change
        )
    )

    return count
