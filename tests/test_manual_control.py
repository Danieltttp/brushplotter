"""Tests del ManualControlWorker. Sin Qt event loop: testamos
directamente los comandos sin pasar por la cola del worker.

El worker en producción procesa comandos en su QThread; en tests
invocamos _handle_command directamente para verificar la lógica.
"""

import pytest

from brushplotter.core.stroke_model import Point
from brushplotter.hardware.simulator import SimulatedController
from brushplotter.workers.manual_control_worker import (
    Command,
    CommandType,
    ManualControlWorker,
)


@pytest.fixture
def worker_with_sim():
    sim = SimulatedController(speed_factor=0.0)
    worker = ManualControlWorker(sim)
    # Simulamos la fase de conexión que normalmente hace run()
    sim.connect()
    sim.enable_motors()
    return worker, sim


def test_jog_moves_cabezal(worker_with_sim):
    worker, sim = worker_with_sim
    worker._handle_command(Command(CommandType.JOG, {"dx": 1.0, "dy": 0.5}))
    pos = sim.get_position()
    assert pos.x == pytest.approx(1.0)
    assert pos.y == pytest.approx(0.5)


def test_jog_is_cumulative(worker_with_sim):
    worker, sim = worker_with_sim
    worker._handle_command(Command(CommandType.JOG, {"dx": 1.0, "dy": 0}))
    worker._handle_command(Command(CommandType.JOG, {"dx": 0.5, "dy": 0.5}))
    assert sim.get_position().x == pytest.approx(1.5)
    assert sim.get_position().y == pytest.approx(0.5)


def test_jog_always_lifts_pen(worker_with_sim):
    worker, sim = worker_with_sim
    sim.pen_down()
    worker._handle_command(Command(CommandType.JOG, {"dx": 1.0, "dy": 0}))
    assert not sim.is_pen_down()


def test_go_to_absolute(worker_with_sim):
    worker, sim = worker_with_sim
    worker._position = Point(5.0, 5.0)
    worker._handle_command(Command(CommandType.GO_TO, {"x": 2.0, "y": 3.0}))
    pos = sim.get_position()
    assert pos.x == pytest.approx(2.0)
    assert pos.y == pytest.approx(3.0)


def test_home_goes_to_origin(worker_with_sim):
    worker, sim = worker_with_sim
    sim.move_to(Point(10.0, 10.0))
    worker._handle_command(Command(CommandType.HOME))
    assert sim.get_position().x == 0.0
    assert sim.get_position().y == 0.0


def test_pen_up_down(worker_with_sim):
    worker, sim = worker_with_sim
    worker._handle_command(Command(CommandType.PEN_DOWN))
    assert sim.is_pen_down()
    worker._handle_command(Command(CommandType.PEN_UP))
    assert not sim.is_pen_down()


def test_dip_test_executes_full_ritual(worker_with_sim):
    """El test de recarga debe: ir al tintero, bajar pincel, hacer
    stirring, hacer bobbing, levantar pincel."""
    worker, sim = worker_with_sim
    initial_count = len(sim.movements)
    worker._handle_command(
        Command(
            CommandType.DIP_TEST,
            {"inkwell": Point(1.0, 1.0), "stirring_radius": 0.04},
        )
    )
    new_movements = sim.movements[initial_count:]
    actions = [m.action for m in new_movements]

    # Debe haber al menos: pen_up, move, pen_down, lines de stirring,
    # pen_up, pen_down (bobbing), pen_up final
    assert "move" in actions
    assert actions.count("pen_down") >= 1
    assert "line" in actions  # stirring
    # El último debería ser pen_up
    assert any(a == "pen_up" for a in actions[-3:])


def test_motors_off_on_emits_correct_commands(worker_with_sim):
    worker, sim = worker_with_sim
    initial_count = len(sim.movements)
    worker._handle_command(Command(CommandType.MOTORS_OFF))
    worker._handle_command(Command(CommandType.MOTORS_ON))
    actions = [m.action for m in sim.movements[initial_count:]]
    assert "motors_off" in actions
    assert "motors_on" in actions
