"""Worker para ejecutar comandos manuales del plotter en un hilo aparte.

A diferencia del PaintWorker (que ejecuta una sesión completa), este
recibe comandos discretos uno a uno desde la GUI (jog, home, dip test,
etc.) y los ejecuta sin bloquear el hilo principal.

Patrón: la GUI llama a métodos públicos (jog, go_to, dip_test...) y el
worker los pone en una cola interna que el hilo procesa secuencialmente.
"""

from __future__ import annotations

import queue
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

try:
    from PySide6.QtCore import QObject, Signal
except ImportError:
    class QObject:
        pass

    class _StubSignal:
        def __init__(self, *args, **kwargs):
            pass

        def emit(self, *args, **kwargs):
            pass

        def connect(self, *args, **kwargs):
            pass

    def Signal(*args, **kwargs):  # noqa: N802
        return _StubSignal()

from ..core.stroke_model import Point
from ..hardware.controller import PlotterController


class CommandType(Enum):
    JOG = "jog"
    GO_TO = "go_to"
    PEN_UP = "pen_up"
    PEN_DOWN = "pen_down"
    HOME = "home"
    DIP_TEST = "dip_test"
    MOTORS_OFF = "motors_off"
    MOTORS_ON = "motors_on"
    SHUTDOWN = "shutdown"


@dataclass
class Command:
    type: CommandType
    data: Optional[dict] = None


class ManualControlWorker(QObject):
    """Procesa comandos manuales secuencialmente en su propio hilo.

    Señales:
        position_changed(float, float): nueva posición física (pulgadas)
        pen_state_changed(bool): True = down, False = up
        command_completed(str): nombre del comando completado
        error(str)
        connection_changed(bool): conectado / desconectado
    """

    position_changed = Signal(float, float)
    pen_state_changed = Signal(bool)
    command_completed = Signal(str)
    error = Signal(str)
    connection_changed = Signal(bool)

    def __init__(self, controller: PlotterController):
        super().__init__()
        self._controller = controller
        self._queue: queue.Queue[Command] = queue.Queue()
        self._running = False
        self._position = Point(0.0, 0.0)
        self._pen_down = False

    # ----------------------------------------------------------
    # API pública (llamada desde el hilo principal)
    # ----------------------------------------------------------
    def jog(self, dx_inches: float, dy_inches: float):
        self._queue.put(Command(CommandType.JOG, {"dx": dx_inches, "dy": dy_inches}))

    def go_to(self, x_inches: float, y_inches: float):
        self._queue.put(Command(CommandType.GO_TO, {"x": x_inches, "y": y_inches}))

    def pen_up(self):
        self._queue.put(Command(CommandType.PEN_UP))

    def pen_down(self):
        self._queue.put(Command(CommandType.PEN_DOWN))

    def home(self):
        self._queue.put(Command(CommandType.HOME))

    def dip_test(self, inkwell: Point, stirring_radius: float = 0.04):
        """Ejecuta el ritual de recarga en una posición, sin pintar.

        Útil para verificar que el cabezal alcanza el tintero correctamente
        antes de empezar una sesión real.
        """
        self._queue.put(
            Command(
                CommandType.DIP_TEST,
                {"inkwell": inkwell, "stirring_radius": stirring_radius},
            )
        )

    def motors_off(self):
        self._queue.put(Command(CommandType.MOTORS_OFF))

    def motors_on(self):
        self._queue.put(Command(CommandType.MOTORS_ON))

    def shutdown(self):
        """Detiene el worker y desconecta el controlador."""
        self._queue.put(Command(CommandType.SHUTDOWN))

    # ----------------------------------------------------------
    # Bucle principal (ejecutado en el QThread del worker)
    # ----------------------------------------------------------
    def run(self):
        try:
            if not self._controller.connect():
                self.error.emit("No se pudo conectar al plotter.")
                return
            self._controller.enable_motors()
            self.connection_changed.emit(True)
            self._running = True

            while self._running:
                try:
                    cmd = self._queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                self._handle_command(cmd)

        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}")
        finally:
            try:
                self._controller.disable_motors()
                self._controller.disconnect()
            except Exception:
                pass
            self.connection_changed.emit(False)

    def _handle_command(self, cmd: Command):
        try:
            if cmd.type == CommandType.JOG:
                new_x = self._position.x + cmd.data["dx"]
                new_y = self._position.y + cmd.data["dy"]
                self._controller.pen_up()
                self._controller.move_to(Point(new_x, new_y))
                self._position = Point(new_x, new_y)
                self.position_changed.emit(new_x, new_y)
                self._pen_down = False
                self.pen_state_changed.emit(False)

            elif cmd.type == CommandType.GO_TO:
                x, y = cmd.data["x"], cmd.data["y"]
                self._controller.pen_up()
                self._controller.move_to(Point(x, y))
                self._position = Point(x, y)
                self.position_changed.emit(x, y)
                self._pen_down = False
                self.pen_state_changed.emit(False)

            elif cmd.type == CommandType.PEN_UP:
                self._controller.pen_up()
                self._pen_down = False
                self.pen_state_changed.emit(False)

            elif cmd.type == CommandType.PEN_DOWN:
                self._controller.pen_down()
                self._pen_down = True
                self.pen_state_changed.emit(True)

            elif cmd.type == CommandType.HOME:
                self._controller.pen_up()
                self._controller.move_to(Point(0.0, 0.0))
                self._position = Point(0.0, 0.0)
                self.position_changed.emit(0.0, 0.0)
                self.pen_state_changed.emit(False)

            elif cmd.type == CommandType.DIP_TEST:
                self._execute_dip_test(
                    cmd.data["inkwell"], cmd.data["stirring_radius"]
                )

            elif cmd.type == CommandType.MOTORS_OFF:
                self._controller.disable_motors()

            elif cmd.type == CommandType.MOTORS_ON:
                self._controller.enable_motors()

            elif cmd.type == CommandType.SHUTDOWN:
                self._running = False
                return

            self.command_completed.emit(cmd.type.value)

        except Exception as e:
            self.error.emit(f"Error en {cmd.type.value}: {e}")

    def _execute_dip_test(self, ink: Point, radius: float):
        """Reproduce el ritual de recarga sin contexto de trazo."""
        self._controller.pen_up()
        self._controller.move_to(ink)
        self.position_changed.emit(ink.x, ink.y)

        self._controller.pen_down()
        self.pen_state_changed.emit(True)
        time.sleep(0.3)

        # Stirring cuadrado
        r = radius * 0.5
        for dx, dy in [(r, 0), (r, r), (0, r), (0, 0)]:
            target = Point(ink.x + dx, ink.y + dy)
            self._controller.line_to(target)
            self.position_changed.emit(target.x, target.y)

        # Bobbing
        self._controller.pen_up()
        time.sleep(0.1)
        self._controller.pen_down()
        time.sleep(0.2)

        self._controller.pen_up()
        self._pen_down = False
        self.pen_state_changed.emit(False)
