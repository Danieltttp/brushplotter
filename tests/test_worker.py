"""Tests del PaintWorker, sin Qt y sin threading."""

import pytest

from brushplotter.core.stroke_model import (
    CanvasGeometry,
    InkColor,
    PaintingSession,
    Point,
    Stroke,
    StrokeStatus,
    WaterStation,
)
from brushplotter.core.svg_loader import load_svg
from brushplotter.hardware.simulator import SimulatedController
from brushplotter.workers.paint_worker import DipPattern, PaintWorker


class AutoAckWorker(PaintWorker):
    """Subclase que auto-confirma cambios de color (sin GUI)."""

    @property
    def _color_change_acknowledged(self):
        return True

    @_color_change_acknowledged.setter
    def _color_change_acknowledged(self, value):
        pass


@pytest.fixture
def two_color_session(tmp_path):
    svg = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
     width="200" height="100" viewBox="0 0 200 100">
  <g inkscape:label="Capa A">
    <path d="M 10 10 L 100 10 L 100 50" stroke="#0066cc" fill="none"/>
  </g>
  <g inkscape:label="Capa B">
    <path d="M 20 80 L 180 80" stroke="#cc0000" fill="none"/>
  </g>
</svg>
"""
    p = tmp_path / "t.svg"
    p.write_text(svg)
    session = load_svg(p)
    for i, cid in enumerate(list(session.colors.keys())):
        session.colors[cid].inkwell_position = Point(1.0, 1.0 + i * 1.5)
    return session


def test_worker_completes_full_session(two_color_session):
    sim = SimulatedController(speed_factor=0.0)
    worker = AutoAckWorker(
        two_color_session, sim,
        dip_pattern=DipPattern(dwell_seconds=0, bob_pause=0, bob_count=0),
    )
    worker.run()
    done = sum(1 for s in two_color_session.strokes if s.status == StrokeStatus.DONE)
    assert done == len(two_color_session.strokes)


def test_worker_logs_color_changes(two_color_session):
    sim = SimulatedController(speed_factor=0.0)
    worker = AutoAckWorker(
        two_color_session, sim,
        dip_pattern=DipPattern(dwell_seconds=0, bob_pause=0, bob_count=0),
    )
    worker.run()
    color_changes = [e for e in two_color_session.event_log if e["type"] == "color_change"]
    assert len(color_changes) >= 2


def test_worker_skips_strokes_without_color():
    session = PaintingSession(svg_file_path="dummy.svg")
    session.svg_min_x, session.svg_max_x = 0, 100
    session.svg_min_y, session.svg_max_y = 0, 100
    session.canvas = CanvasGeometry(start_x=1, start_y=1, drawing_width=2)
    session.strokes = [Stroke(points=[(0, 0), (50, 50)], color_id=None)]

    sim = SimulatedController(speed_factor=0.0)
    worker = PaintWorker(session, sim, dip_pattern=DipPattern(dwell_seconds=0))
    worker.run()

    assert session.strokes[0].status == StrokeStatus.SKIPPED
    line_movements = [m for m in sim.movements if m.action == "line"]
    assert len(line_movements) == 0


def test_worker_emits_dip_when_distance_exceeded():
    session = PaintingSession(svg_file_path="dummy.svg")
    session.svg_min_x, session.svg_max_x = 0, 10
    session.svg_min_y, session.svg_max_y = 0, 10
    session.canvas = CanvasGeometry(start_x=2, start_y=2, drawing_width=10)
    session.material_profile.max_draw_distance_inches = 3.0
    session.strokes = [Stroke(points=[(i, 0) for i in range(0, 11)], color_id="azul")]
    session.colors["azul"] = InkColor(
        name="Azul", hex="#0000ff", inkwell_position=Point(1, 1)
    )

    sim = SimulatedController(speed_factor=0.0)
    worker = AutoAckWorker(
        session, sim,
        dip_pattern=DipPattern(dwell_seconds=0, bob_pause=0, bob_count=0),
    )
    worker.run()

    dips = [e for e in session.event_log if e["type"] == "dip"]
    assert len(dips) >= 3


def test_worker_water_dip_when_enabled(tmp_path):
    """Si uses_water_before_dip=True y hay water_station calibrada, el
    worker debe pasar por agua antes de cada recarga de color."""
    svg = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">
  <path d="M 10 10 L 90 90" stroke="#0066cc" fill="none"/>
</svg>
"""
    p = tmp_path / "wd.svg"
    p.write_text(svg)
    session = load_svg(p)
    cid = next(iter(session.colors.keys()))
    session.colors[cid].inkwell_position = Point(1.0, 1.0)
    session.water_station = WaterStation(position=Point(0.5, 0.5))
    session.material_profile.uses_water_before_dip = True
    session.material_profile.water_dwell_seconds = 0
    session.material_profile.water_bob_count = 0
    session.material_profile.max_draw_distance_inches = 1.0
    sim = SimulatedController(speed_factor=0.0)
    worker = AutoAckWorker(
        session, sim, dip_pattern=DipPattern(dwell_seconds=0, bob_pause=0, bob_count=0)
    )
    worker.run()
    water_events = [e for e in session.event_log if e["type"] == "water_dip"]
    dip_events = [e for e in session.event_log if e["type"] == "dip"]
    assert len(water_events) >= 1
    assert len(water_events) == len(dip_events)


def test_worker_skips_water_when_not_calibrated(tmp_path):
    """Si uses_water_before_dip=True pero la water_station no tiene
    posición, el ritual se omite silenciosamente."""
    svg = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="50mm" height="50mm" viewBox="0 0 50 50">
  <path d="M 5 5 L 45 45" stroke="#0066cc" fill="none"/>
</svg>
"""
    p = tmp_path / "nw.svg"
    p.write_text(svg)
    session = load_svg(p)
    cid = next(iter(session.colors.keys()))
    session.colors[cid].inkwell_position = Point(1.0, 1.0)
    session.material_profile.uses_water_before_dip = True
    session.material_profile.max_draw_distance_inches = 0.5
    sim = SimulatedController(speed_factor=0.0)
    worker = AutoAckWorker(
        session, sim, dip_pattern=DipPattern(dwell_seconds=0, bob_pause=0, bob_count=0)
    )
    worker.run()
    water_events = [e for e in session.event_log if e["type"] == "water_dip"]
    assert len(water_events) == 0


def test_worker_skips_water_when_disabled(tmp_path):
    """Si uses_water_before_dip=False, no se hace ritual de agua aunque
    esté calibrada."""
    svg = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="50mm" height="50mm" viewBox="0 0 50 50">
  <path d="M 5 5 L 45 45" stroke="#0066cc" fill="none"/>
</svg>
"""
    p = tmp_path / "dw.svg"
    p.write_text(svg)
    session = load_svg(p)
    cid = next(iter(session.colors.keys()))
    session.colors[cid].inkwell_position = Point(1.0, 1.0)
    session.water_station = WaterStation(position=Point(0.5, 0.5))
    session.material_profile.uses_water_before_dip = False
    session.material_profile.uses_water_on_color_change = False
    session.material_profile.max_draw_distance_inches = 0.5
    sim = SimulatedController(speed_factor=0.0)
    worker = AutoAckWorker(
        session, sim, dip_pattern=DipPattern(dwell_seconds=0, bob_pause=0, bob_count=0)
    )
    worker.run()
    water_events = [e for e in session.event_log if e["type"] == "water_dip"]
    deep_events = [e for e in session.event_log if e["type"] == "deep_water_dip"]
    assert len(water_events) == 0
    assert len(deep_events) == 0


def test_worker_deep_water_ritual_on_color_change(tmp_path):
    """Si uses_water_on_color_change=True, debe hacerse limpieza profunda
    cada vez que cambia el color (excepto al empezar la sesión)."""
    svg = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">
  <path d="M 10 10 L 40 40" stroke="#0066cc" fill="none"/>
  <path d="M 50 50 L 90 90" stroke="#cc0000" fill="none"/>
  <path d="M 30 70 L 70 30" stroke="#0066cc" fill="none"/>
</svg>
"""
    p = tmp_path / "dc.svg"
    p.write_text(svg)
    session = load_svg(p)
    for cid in session.colors:
        session.colors[cid].inkwell_position = Point(1.0, 1.0 + len(cid))
    session.water_station = WaterStation(position=Point(0.5, 0.5))
    session.material_profile.uses_water_before_dip = False
    session.material_profile.uses_water_on_color_change = True
    session.material_profile.deep_water_dwell_seconds = 0
    session.material_profile.deep_water_air_dry_seconds = 0
    session.material_profile.deep_water_bob_count = 0
    session.material_profile.deep_water_stirring_passes = 1
    session.material_profile.max_draw_distance_inches = 100.0  # sin recargas
    sim = SimulatedController(speed_factor=0.0)
    worker = AutoAckWorker(
        session, sim, dip_pattern=DipPattern(dwell_seconds=0, bob_pause=0, bob_count=0)
    )
    worker.run()
    deep_events = [e for e in session.event_log if e["type"] == "deep_water_dip"]
    color_changes = [e for e in session.event_log if e["type"] == "color_change"]
    # Cambios de color: None→azul, azul→rojo, rojo→azul = 3
    # Pero el primer cambio (None→algo) NO dispara limpieza profunda.
    # Esperamos: 2 limpiezas profundas
    assert len(color_changes) == 3
    assert len(deep_events) == 2


def test_worker_no_deep_water_at_session_start(tmp_path):
    """La limpieza profunda solo se dispara entre colores reales,
    no al pasar de 'sin color previo' al primer color de la sesión."""
    svg = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="50mm" height="50mm" viewBox="0 0 50 50">
  <path d="M 5 5 L 45 45" stroke="#0066cc" fill="none"/>
</svg>
"""
    p = tmp_path / "ss.svg"
    p.write_text(svg)
    session = load_svg(p)
    cid = next(iter(session.colors.keys()))
    session.colors[cid].inkwell_position = Point(1.0, 1.0)
    session.water_station = WaterStation(position=Point(0.5, 0.5))
    session.material_profile.uses_water_on_color_change = True
    session.material_profile.uses_water_before_dip = False
    session.material_profile.max_draw_distance_inches = 100.0
    sim = SimulatedController(speed_factor=0.0)
    worker = AutoAckWorker(
        session, sim, dip_pattern=DipPattern(dwell_seconds=0, bob_pause=0, bob_count=0)
    )
    worker.run()
    deep_events = [e for e in session.event_log if e["type"] == "deep_water_dip"]
    assert len(deep_events) == 0
