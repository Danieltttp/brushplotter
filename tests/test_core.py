"""Tests del núcleo. Ejecutar con: pytest brushplotter/tests/

Demuestran que toda la lógica funciona sin necesidad de plotter físico.
"""

import math
from pathlib import Path

import pytest

from brushplotter.core.stroke_model import (
    CanvasGeometry,
    InkColor,
    PaintingSession,
    Point,
    Stroke,
    StrokeStatus,
    inches_to_mm,
    mm_to_inches,
)
from brushplotter.core.svg_loader import (
    flatten_path,
    load_svg,
    subdivide_long_segments,
)
from brushplotter.hardware.simulator import SimulatedController


# ---------------------------------------------------------------
# Conversión de unidades
# ---------------------------------------------------------------
def test_mm_inch_roundtrip():
    assert mm_to_inches(inches_to_mm(1.0)) == pytest.approx(1.0)
    assert inches_to_mm(1.0) == pytest.approx(25.4)


# ---------------------------------------------------------------
# Subdivisión de segmentos largos
# ---------------------------------------------------------------
def test_subdivide_respects_max_length():
    points = [(0, 0), (10, 0)]
    result = subdivide_long_segments(points, max_len=2.0)
    # Distancia 10, max 2 -> 5 subsegmentos -> 6 puntos
    assert len(result) == 6
    # Cada subsegmento ≤ 2
    for i in range(1, len(result)):
        x0, y0 = result[i - 1]
        x1, y1 = result[i]
        assert math.hypot(x1 - x0, y1 - y0) <= 2.0 + 1e-9


def test_subdivide_leaves_short_segments_alone():
    points = [(0, 0), (1, 0), (2, 0)]
    result = subdivide_long_segments(points, max_len=10.0)
    assert result == points


def test_subdivide_handles_degenerate():
    assert subdivide_long_segments([], 1.0) == []
    assert subdivide_long_segments([(0, 0)], 1.0) == [(0, 0)]


# ---------------------------------------------------------------
# Aplanado de paths
# ---------------------------------------------------------------
def test_flatten_handles_bezier():
    """Una curva Bézier debe producir N+1 puntos, no descartarse."""
    from svgpathtools import CubicBezier, Path

    bezier = CubicBezier(0 + 0j, 1 + 1j, 2 + 1j, 3 + 0j)
    path = Path(bezier)
    points = flatten_path(path, samples=10)
    # 1 punto inicial + 10 muestras de la curva
    assert len(points) == 11
    assert points[0] == (0.0, 0.0)
    assert points[-1] == pytest.approx((3.0, 0.0))


# ---------------------------------------------------------------
# Modelo PaintingSession
# ---------------------------------------------------------------
def test_session_scale_and_projection():
    """La proyección usa el viewBox del SVG + escala del usuario.

    Nueva semántica (v0.0.5+): scale = (native_inches / viewbox_width)
    * scale_factor. El origen es (0,0) del viewBox, no del bounding
    box de los trazos.
    """
    s = PaintingSession(svg_file_path="dummy.svg")
    # ViewBox de 100×50 unidades; nativo: 10 pulgadas de ancho.
    # Por tanto, 1 unidad SVG = 0.1 pulgadas físicas a escala 100%.
    s.svg_min_x, s.svg_max_x = 0, 100
    s.svg_min_y, s.svg_max_y = 0, 50
    s.svg_native_width_inches = 10.0
    s.svg_native_height_inches = 5.0
    s.canvas = CanvasGeometry(
        start_x=1.0, start_y=2.0,
        drawing_width=10.0, scale_factor=1.0,
    )
    assert s.scale == pytest.approx(0.1)
    assert s.physical_height == pytest.approx(5.0)
    assert s.physical_width == pytest.approx(10.0)

    # Proyección de (50, 25) -> (1.0 + 50*0.1, 2.0 + 25*0.1)
    p = s.svg_to_physical(50, 25)
    assert p.x == pytest.approx(6.0)
    assert p.y == pytest.approx(4.5)


def test_session_respects_full_canvas_not_bounding_box():
    """Si los trazos están en un sub-área del viewBox, la proyección
    debe respetar la posición real dentro del viewBox, no encajarlos
    en el origen."""
    s = PaintingSession(svg_file_path="dummy.svg")
    # ViewBox A4 entero: 210×297 (en mm = unidades SVG)
    s.svg_min_x, s.svg_max_x = 0, 210
    s.svg_min_y, s.svg_max_y = 0, 297
    # SVG nativo en pulgadas
    s.svg_native_width_inches = 210 / 25.4   # 8.27"
    s.svg_native_height_inches = 297 / 25.4  # 11.69"
    s.canvas = CanvasGeometry(
        start_x=0.0, start_y=0.0,
        drawing_width=8.27, scale_factor=1.0,
    )
    # Un punto en el centro del viewBox debe estar en el centro físico,
    # incluso si los trazos reales del SVG están todos arriba a la izq.
    p = s.svg_to_physical(105, 148.5)  # centro del A4
    # Debería caer en 4.13" × 5.85" (centro físico)
    assert p.x == pytest.approx(105 / 25.4, abs=0.01)
    assert p.y == pytest.approx(148.5 / 25.4, abs=0.01)


def test_session_rotation_90_degrees():
    """Con rotación 90°, un punto en (max_x, 0) debe ir a (0, 0) y
    (0, 0) debe ir a (max_x, ...) — rotación antihoraria."""
    s = PaintingSession(svg_file_path="dummy.svg")
    s.svg_min_x, s.svg_max_x = 0, 100
    s.svg_min_y, s.svg_max_y = 0, 50
    s.svg_native_width_inches = 10.0
    s.svg_native_height_inches = 5.0
    s.canvas = CanvasGeometry(
        start_x=0.0, start_y=0.0,
        drawing_width=10.0, scale_factor=1.0,
        rotation_degrees=90,
    )
    # (0, 0) en SVG con rotación 90° -> (0, svg_max_x*scale) = (0, 10")
    p_origin = s.svg_to_physical(0, 0)
    assert p_origin.x == pytest.approx(0.0, abs=0.01)
    assert p_origin.y == pytest.approx(10.0, abs=0.01)
    # (100, 0) en SVG con rotación 90° -> (0, 0) tras la fórmula
    # rotation_degrees=90: (x, y) -> (y, svg_max_x - x)
    # (100, 0) -> (0, 0)
    p_topright = s.svg_to_physical(100, 0)
    assert p_topright.x == pytest.approx(0.0, abs=0.01)
    assert p_topright.y == pytest.approx(0.0, abs=0.01)


def test_session_progress():
    s = PaintingSession(svg_file_path="dummy.svg")
    s.strokes = [Stroke(points=[(0, 0), (1, 0)]) for _ in range(4)]
    assert s.progress_fraction == 0.0
    s.strokes[0].status = StrokeStatus.DONE
    s.strokes[1].status = StrokeStatus.DONE
    assert s.progress_fraction == 0.5


def test_session_detects_uncalibrated_colors():
    s = PaintingSession(svg_file_path="dummy.svg")
    s.colors = {
        "azul": InkColor(name="Azul", hex="#0000ff"),  # sin posición
        "rojo": InkColor(name="Rojo", hex="#ff0000", inkwell_position=Point(1, 1)),
    }
    s.strokes = [
        Stroke(points=[(0, 0), (1, 0)], color_id="azul"),
        Stroke(points=[(0, 0), (1, 0)], color_id="rojo"),
        Stroke(points=[(0, 0), (1, 0)], color_id=None),  # sin asignar
    ]
    uncal = s.uncalibrated_colors
    assert len(uncal) == 1
    assert uncal[0].name == "Azul"
    assert s.unassigned_stroke_count == 1


def test_event_log():
    s = PaintingSession(svg_file_path="dummy.svg")
    s.log_event("stroke_done", stroke_index=5)
    s.log_event("dip", color_id="azul")
    assert len(s.event_log) == 2
    assert s.event_log[0]["type"] == "stroke_done"
    assert s.event_log[0]["stroke_index"] == 5
    assert "timestamp" in s.event_log[0]


# ---------------------------------------------------------------
# Carga de SVG (con archivo de prueba sintético)
# ---------------------------------------------------------------
@pytest.fixture
def sample_svg(tmp_path):
    """SVG mínimo con un path con curva Bézier y un path con stroke de color."""
    svg = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
     width="200" height="100" viewBox="0 0 200 100">
  <g inkscape:label="Capa azul" id="g_azul">
    <path id="p1" d="M 10 10 L 100 10 L 100 50" stroke="#0066cc" fill="none"/>
    <path id="p2" d="M 10 60 C 50 30, 100 80, 150 60" stroke="#0066cc" fill="none"/>
  </g>
  <g inkscape:label="Capa roja" id="g_roja">
    <path id="p3" d="M 20 80 L 180 80" stroke="#cc0000" fill="none"/>
  </g>
</svg>
"""
    path = tmp_path / "test.svg"
    path.write_text(svg)
    return path


def test_load_svg_basic(sample_svg):
    session = load_svg(sample_svg)
    assert len(session.strokes) == 3
    # Dos colores detectados automáticamente
    assert len(session.colors) == 2


def test_load_svg_assigns_layer(sample_svg):
    session = load_svg(sample_svg)
    layers = {s.source_layer for s in session.strokes}
    assert "Capa azul" in layers
    assert "Capa roja" in layers


def test_load_svg_flattens_bezier(sample_svg):
    session = load_svg(sample_svg)
    # El path con Bézier debe tener muchos más de 2 puntos
    bezier_strokes = [s for s in session.strokes if "60" in str(s.points[0])]
    assert any(len(s.points) > 10 for s in bezier_strokes)


def test_load_svg_bounding_box(sample_svg):
    session = load_svg(sample_svg)
    assert session.svg_min_x >= 0
    assert session.svg_max_x <= 200
    assert session.svg_min_y >= 0
    assert session.svg_max_y <= 100


# ---------------------------------------------------------------
# Simulador
# ---------------------------------------------------------------
def test_simulator_records_movements():
    sim = SimulatedController()
    assert sim.connect()
    sim.move_to(Point(1.0, 2.0))
    sim.pen_down()
    sim.line_to(Point(3.0, 4.0))
    sim.pen_up()
    sim.disconnect()

    actions = [m.action for m in sim.movements]
    assert "connect" in actions
    assert "move" in actions
    assert "pen_down" in actions
    assert "line" in actions
    assert "pen_up" in actions

    # Posición final
    assert sim.get_position().x == 3.0
    assert sim.get_position().y == 4.0


def test_simulator_pen_state():
    sim = SimulatedController()
    sim.connect()
    assert not sim.is_pen_down()
    sim.pen_down()
    assert sim.is_pen_down()
    sim.pen_up()
    assert not sim.is_pen_down()


def test_load_svg_assigns_default_color_when_no_stroke(tmp_path):
    """Si el SVG no tiene strokes definidos, debe crearse un color por
    defecto y asignarlo a todos los trazos para que la app funcione."""
    svg = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <path d="M 10 10 L 50 50"/>
  <path d="M 50 50 L 90 10"/>
</svg>
"""
    p = tmp_path / "no_stroke.svg"
    p.write_text(svg)
    session = load_svg(p)
    assert len(session.strokes) == 2
    assert len(session.colors) == 1
    for s in session.strokes:
        assert s.color_id is not None
