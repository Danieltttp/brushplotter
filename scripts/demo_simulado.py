"""Demo end-to-end con el simulador. Sin hardware necesario.

Ejecutar desde la raíz del proyecto:
    python -m brushplotter.scripts.demo_simulado

Demuestra el flujo completo:
1. Carga un SVG.
2. Asigna posiciones a los tinteros.
3. Aplica un perfil de material.
4. Ejecuta la pintura sobre el simulador, contando recargas.
5. Imprime un resumen.
"""

import math
import tempfile
from pathlib import Path

from brushplotter.core.stroke_model import InkColor, MaterialProfile, Point
from brushplotter.core.svg_loader import load_svg
from brushplotter.hardware.simulator import SimulatedController


SAMPLE_SVG = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
     width="400" height="300" viewBox="0 0 400 300">
  <g inkscape:label="Trazos azules">
    <path d="M 50 50 C 100 20, 200 80, 300 50 S 380 100, 380 150" stroke="#185FA5" fill="none"/>
    <path d="M 60 100 L 350 100 L 350 130 L 60 130 Z" stroke="#185FA5" fill="none"/>
  </g>
  <g inkscape:label="Trazos tierra">
    <path d="M 80 180 Q 200 150 320 180 T 380 220" stroke="#993C1D" fill="none"/>
    <path d="M 100 250 L 300 250" stroke="#993C1D" fill="none"/>
  </g>
</svg>
"""


def simulate_session(session, controller, profile):
    """Bucle de pintura simplificado (sin ritual de dip por brevedad).

    Cuenta cuántas veces se habría disparado una recarga.
    """
    controller.connect()
    controller.enable_motors()
    controller.apply_profile(profile)

    max_dist = profile.max_draw_distance_inches
    distance_drawn = 0.0
    dip_count = 0
    current_color_id = None

    for idx, stroke in enumerate(session.strokes):
        if stroke.color_id is None:
            continue  # Sin color asignado, no se pinta

        # Cambio de color → pausa virtual + recarga
        if stroke.color_id != current_color_id:
            color = session.colors[stroke.color_id]
            if color.inkwell_position:
                controller.pen_up()
                controller.move_to(color.inkwell_position)
                dip_count += 1
                distance_drawn = 0.0
            current_color_id = stroke.color_id

        start = session.svg_to_physical(*stroke.points[0])
        controller.pen_up()
        controller.move_to(start)
        controller.pen_down()

        for i in range(1, len(stroke.points)):
            prev = session.svg_to_physical(*stroke.points[i - 1])
            curr = session.svg_to_physical(*stroke.points[i])
            seg = math.hypot(curr.x - prev.x, curr.y - prev.y)

            if distance_drawn + seg > max_dist:
                color = session.colors[current_color_id]
                if color.inkwell_position:
                    controller.pen_up()
                    controller.move_to(color.inkwell_position)
                    controller.move_to(curr)
                    controller.pen_down()
                    dip_count += 1
                    distance_drawn = 0.0

            controller.line_to(curr)
            distance_drawn += seg

        controller.pen_up()
        from brushplotter.core.stroke_model import StrokeStatus
        stroke.status = StrokeStatus.DONE

    controller.move_to(Point(0, 0))
    controller.disable_motors()
    controller.disconnect()

    return dip_count


def main():
    print("=" * 60)
    print("Demo: brushplotter con simulador")
    print("=" * 60)

    # 1. SVG temporal
    with tempfile.NamedTemporaryFile(suffix=".svg", mode="w", delete=False) as f:
        f.write(SAMPLE_SVG)
        svg_path = f.name

    # 2. Carga
    session = load_svg(svg_path)
    print(f"\n→ SVG cargado: {len(session.strokes)} trazos")
    print(f"  Bounding box: ({session.svg_min_x:.1f}, {session.svg_min_y:.1f}) "
          f"- ({session.svg_max_x:.1f}, {session.svg_max_y:.1f})")
    print(f"  Colores detectados automáticamente: {len(session.colors)}")
    for cid, color in session.colors.items():
        print(f"    · {cid}: {color.hex}")

    # 3. Asignar posiciones de tintero a los colores detectados
    inkwell_positions = [Point(1.0, 1.0), Point(1.0, 2.5)]
    for (cid, color), pos in zip(session.colors.items(), inkwell_positions):
        color.inkwell_position = pos
        color.name = f"Tintero {cid}"

    print(f"\n→ Escala: 1 unidad SVG = {session.scale:.4f} pulgadas")
    print(f"  Dimensiones físicas: {session.canvas.drawing_width:.1f}\" x "
          f"{session.physical_height:.1f}\"")

    # 4. Ejecutar sobre simulador
    sim = SimulatedController(speed_factor=0.0)  # Instantáneo
    profile = MaterialProfile(name="Demo", max_draw_distance_inches=2.0)
    print(f"\n→ Perfil: {profile.name}, recarga cada {profile.max_draw_distance_inches}\"")
    print(f"  Ejecutando sobre simulador...")

    dip_count = simulate_session(session, sim, profile)

    # 5. Resumen
    print(f"\n→ Ejecución completa:")
    print(f"  Movimientos totales registrados: {len(sim.movements)}")
    print(f"  Recargas de pintura simuladas: {dip_count}")
    print(f"  Trazos completados: "
          f"{sum(1 for s in session.strokes if s.status.value == 'done')}/{len(session.strokes)}")
    print(f"  Posición final del cabezal: "
          f"({sim.get_position().x:.2f}, {sim.get_position().y:.2f})")

    # Limpieza
    Path(svg_path).unlink()

    print(f"\n{'=' * 60}")
    print("Demo terminada. Sin un solo motor encendido.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
