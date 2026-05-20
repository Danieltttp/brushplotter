"""Simulador del plotter para desarrollo sin hardware.

Implementa la misma interfaz que el controlador real pero solo registra
movimientos en una lista. Permite desarrollar y testear la GUI completa
sin tener el plotter conectado.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..core.stroke_model import MaterialProfile, Point
from .controller import PlotterController


@dataclass
class MovementRecord:
    timestamp: float
    action: str  # 'move' | 'line' | 'pen_up' | 'pen_down' | 'motors_on' | 'motors_off'
    point: Point | None = None
    pen_down: bool = False


@dataclass
class SimulatedController(PlotterController):
    """Plotter virtual. Útil para tests y desarrollo de GUI.

    speed_factor: 0.0 = instantáneo (tests), 1.0 = velocidad real
    estimada. Útil para previsualizar tiempos en la GUI.
    """

    speed_factor: float = 0.0
    movements: list[MovementRecord] = field(default_factory=list)
    _connected: bool = False
    _position: Point = field(default_factory=lambda: Point(0.0, 0.0))
    _pen_down: bool = False
    _motors_on: bool = False
    _current_speed_pendown: int = 5
    _current_speed_penup: int = 40

    def _record(self, action: str, point: Point | None = None):
        self.movements.append(
            MovementRecord(
                timestamp=time.time(),
                action=action,
                point=point,
                pen_down=self._pen_down,
            )
        )

    def _simulate_travel(self, dest: Point):
        if self.speed_factor <= 0:
            return
        import math
        dist = math.hypot(dest.x - self._position.x, dest.y - self._position.y)
        # Velocidades en "%" del plotter: aproximamos pulgadas/segundo
        # como speed_pct * 0.4 (calibración aproximada NextDraw).
        speed_pct = (
            self._current_speed_pendown if self._pen_down else self._current_speed_penup
        )
        speed_ips = max(speed_pct * 0.4, 0.1)
        time.sleep((dist / speed_ips) * self.speed_factor)

    def connect(self) -> bool:
        self._connected = True
        self._record("connect")
        return True

    def disconnect(self) -> None:
        self._connected = False
        self._record("disconnect")

    def apply_profile(self, profile: MaterialProfile) -> None:
        self._current_speed_pendown = profile.speed_pendown
        self._current_speed_penup = profile.speed_penup
        self._record("apply_profile")

    def pen_up(self) -> None:
        self._pen_down = False
        self._record("pen_up")

    def pen_down(self) -> None:
        self._pen_down = True
        self._record("pen_down")

    def move_to(self, point: Point) -> None:
        self._simulate_travel(point)
        self._record("move", point)
        self._position = point

    def line_to(self, point: Point) -> None:
        self._simulate_travel(point)
        self._record("line", point)
        self._position = point

    def disable_motors(self) -> None:
        self._motors_on = False
        self._record("motors_off")

    def enable_motors(self) -> None:
        self._motors_on = True
        self._record("motors_on")

    def get_position(self) -> Point:
        return self._position

    def is_pen_down(self) -> bool:
        return self._pen_down
