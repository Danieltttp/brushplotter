"""Interfaz abstracta del controlador del plotter.

Define el contrato que implementan tanto el controlador real (NextDraw)
como el simulador. La GUI y los workers nunca importan nextdraw
directamente; siempre dependen de esta interfaz.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ..core.stroke_model import MaterialProfile, Point


class PlotterController(ABC):
    """Contrato del controlador del plotter.

    Implementaciones: NextDrawController (hardware real) y
    SimulatedController (para desarrollo sin plotter).
    """

    @abstractmethod
    def connect(self) -> bool:
        """Establece conexión con el dispositivo. True si éxito."""

    @abstractmethod
    def disconnect(self) -> None:
        """Cierra conexión y libera motores."""

    @abstractmethod
    def apply_profile(self, profile: MaterialProfile) -> None:
        """Aplica un perfil de material (velocidades, presión)."""

    @abstractmethod
    def pen_up(self) -> None:
        """Levanta el pincel."""

    @abstractmethod
    def pen_down(self) -> None:
        """Baja el pincel."""

    @abstractmethod
    def move_to(self, point: Point) -> None:
        """Mueve el cabezal (con pen-up o pen-down según estado)."""

    @abstractmethod
    def line_to(self, point: Point) -> None:
        """Dibuja una línea hasta el punto."""

    @abstractmethod
    def disable_motors(self) -> None:
        """Apaga motores (permite mover el cabezal a mano)."""

    @abstractmethod
    def enable_motors(self) -> None:
        """Enciende motores en modo interactivo."""

    @abstractmethod
    def get_position(self) -> Point:
        """Devuelve la posición actual del cabezal."""

    @abstractmethod
    def is_pen_down(self) -> bool:
        """Estado actual del pincel."""
