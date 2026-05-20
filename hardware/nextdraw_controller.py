"""Controlador real del NextDraw envolviendo el SDK oficial.

Importa nextdraw de forma lazy: el módulo es importable aunque el SDK
no esté instalado (necesario para tests y desarrollo sin hardware).
"""

from __future__ import annotations

import time

from ..core.stroke_model import MaterialProfile, Point
from .controller import PlotterController


class NextDrawController(PlotterController):
    """Controlador del NextDraw vía SDK oficial de Bantam Tools.

    Usa el modo interactivo de la API para tener control fino sobre
    cada movimiento (necesario para el ritual de recarga de pintura).
    """

    def __init__(self):
        # Import lazy: el SDK puede no estar instalado en entornos de dev
        try:
            from nextdraw import NextDraw
        except ImportError as e:
            raise RuntimeError(
                "SDK nextdraw no instalado. Ejecuta:\n"
                "pip install https://software-download.bantamtools.com/nd/api/nextdraw_api.zip"
            ) from e

        self._nd = NextDraw()
        self._nd.interactive()
        self._pen_down = False
        self._position = Point(0.0, 0.0)
        self._connected = False

    def connect(self) -> bool:
        # Configuración por defecto antes de conectar
        self._nd.options.homing = True

        if not self._nd.connect():
            return False
        self._connected = True
        return True

    def disconnect(self) -> None:
        if self._connected:
            try:
                self._nd.disconnect()
            except Exception:
                pass
            self._connected = False

    def apply_profile(self, profile: MaterialProfile) -> None:
        self._nd.options.speed_pendown = profile.speed_pendown
        self._nd.options.speed_penup = profile.speed_penup
        self._nd.options.pen_pos_down = profile.pen_pos_down
        self._nd.options.pen_pos_up = profile.pen_pos_up
        self._nd.options.pen_rate_lower = profile.pen_rate_lower
        self._nd.options.pen_rate_raise = profile.pen_rate_raise

    def pen_up(self) -> None:
        self._nd.penup()
        self._pen_down = False

    def pen_down(self) -> None:
        self._nd.pendown()
        self._pen_down = True

    def move_to(self, point: Point) -> None:
        self._nd.moveto(point.x, point.y)
        self._position = point

    def line_to(self, point: Point) -> None:
        self._nd.lineto(point.x, point.y)
        self._position = point

    def disable_motors(self) -> None:
        try:
            self._nd.usb_command("EM,0,0")
        except Exception:
            pass

    def enable_motors(self) -> None:
        try:
            self._nd.usb_command("EM,1,1")
            time.sleep(0.5)
        except Exception:
            pass

    def get_position(self) -> Point:
        return self._position

    def is_pen_down(self) -> bool:
        return self._pen_down
