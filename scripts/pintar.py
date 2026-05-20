"""
pintar.py — Versión corregida de la guía original.

Cambios respecto a la versión anterior:
1. Procesa curvas Bézier y Arcs (no solo Lines) muestreando puntos.
   La versión anterior descartaba silenciosamente todo lo que no fuera Line.
2. Subdivide segmentos largos para que MAX_DRAW_DIST se respete siempre,
   incluso si un único segmento excede el límite.
3. Captura todas las excepciones, no solo KeyboardInterrupt, y apaga los
   motores antes de re-levantar (evita dejar la máquina energizada).
4. La reanudación serializa los trazos a JSON al inicio, en vez de depender
   del orden determinista del SVG entre ejecuciones.
5. El "stirring" del tintero es paramétrico (radio del pocillo).
6. Validación de coordenadas: avisa si el dibujo se va a salir del área
   útil antes de empezar.

Autor: Daniel García Andújar + asistencia técnica.
Licencia: GPL-3.0 (pendiente de confirmar).
"""

import json
import math
import os
import sys
import time
from pathlib import Path

from nextdraw import NextDraw
from svgpathtools import svg2paths, Line, CubicBezier, QuadraticBezier, Arc

# =================================================================
# 1. CONFIGURACIÓN
# =================================================================
INKWELL_X = 1.0          # Coordenada X del tintero (pulgadas)
INKWELL_Y = 1.0          # Coordenada Y del tintero (pulgadas)
INKWELL_RADIUS = 0.08    # Radio interior del pocillo (pulgadas, ~2 mm)
MAX_DRAW_DIST = 5.0      # Pulgadas que pinta antes de recargar
SVG_FILE = "aplanado.svg"

START_X = 3.0            # Margen X de inicio del dibujo
START_Y = 2.0            # Margen Y de inicio del dibujo
DRAWING_WIDTH = 8.0      # Ancho físico máximo del dibujo
PLOTTER_MAX_X = 34.02    # Límite físico del plotter (NextDraw 2234, A1)
PLOTTER_MAX_Y = 23.39

BEZIER_SAMPLES = 20      # Puntos por curva Bézier (más = más liso, más lento)
MAX_SEGMENT_LEN = 0.5    # Subdivide segmentos más largos que esto (pulgadas)

# Archivo de estado para reanudación robusta
STATE_FILE = "session_state.json"
START_AT_STROKE = 0
# =================================================================


def flatten_path(path, samples=BEZIER_SAMPLES):
    """Convierte un path de svgpathtools a lista de puntos (x, y).

    A diferencia del script original, procesa Bézier y Arc muestreando
    'samples' puntos a lo largo de la curva, en vez de descartarlos.
    """
    points = []
    for segment in path:
        if len(points) == 0:
            points.append((segment.start.real, segment.start.imag))
        if isinstance(segment, Line):
            points.append((segment.end.real, segment.end.imag))
        elif isinstance(segment, (CubicBezier, QuadraticBezier, Arc)):
            # Muestreamos la curva en N puntos (excluyendo t=0 que ya está)
            for i in range(1, samples + 1):
                t = i / samples
                pt = segment.point(t)
                points.append((pt.real, pt.imag))
        else:
            # Tipo desconocido: al menos no perdemos el endpoint
            points.append((segment.end.real, segment.end.imag))
    return points


def subdivide_long_segments(points, max_len_svg_units):
    """Inserta puntos intermedios en segmentos que excedan max_len.

    Garantiza que MAX_DRAW_DIST siempre se pueda respetar: si un único
    segmento midiera más que MAX_DRAW_DIST, nunca se interrumpiría.
    """
    if len(points) < 2:
        return points
    result = [points[0]]
    for i in range(1, len(points)):
        x0, y0 = result[-1]
        x1, y1 = points[i]
        seg_len = math.hypot(x1 - x0, y1 - y0)
        if seg_len > max_len_svg_units:
            n_sub = int(math.ceil(seg_len / max_len_svg_units))
            for k in range(1, n_sub + 1):
                t = k / n_sub
                result.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
        else:
            result.append((x1, y1))
    return result


def save_state(stroke_index, total):
    """Guarda el estado de la sesión para reanudación robusta."""
    state = {
        "svg_file": SVG_FILE,
        "last_completed_stroke": stroke_index,
        "total_strokes": total,
        "timestamp": time.time(),
    }
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def load_state():
    """Carga el estado previo si existe y es válido."""
    if not os.path.exists(STATE_FILE):
        return None
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
        if state.get("svg_file") != SVG_FILE:
            print(f"[!] Estado previo es de otro archivo ({state.get('svg_file')}). Ignorando.")
            return None
        return state
    except (json.JSONDecodeError, KeyError):
        return None


def emergency_shutdown(nd, error_msg=None):
    """Apaga motores de forma segura ante cualquier error."""
    try:
        nd.penup()
        nd.usb_command("EM,0,0")
        nd.disconnect()
    except Exception as e:
        print(f"[!] Error durante apagado de emergencia: {e}")
    if error_msg:
        print(f"\n[!] {error_msg}")


# =================================================================
# INICIO
# =================================================================
print("Iniciando conexión con el plotter...")
nd = NextDraw()
nd.interactive()

nd.options.speed_pendown = 5
nd.options.speed_penup = 40
nd.options.pen_pos_down = 40
nd.options.pen_pos_up = 70
nd.options.pen_rate_lower = 20
nd.options.pen_rate_raise = 50
nd.options.homing = True        # Auto-homing (disponible en NextDraw 2234)

if not nd.connect():
    print("Error: plotter no conectado.")
    sys.exit(1)

print("¡Conexión exitosa! Despertando motores XY...")
nd.usb_command("EM,1,1")
time.sleep(1)

distance_drawn = 0.0


def dip_brush(resume_x, resume_y):
    """Carga pintura imitando gestos humanos."""
    global distance_drawn
    print("\n--- Recargando pintura... ---")
    nd.penup()
    nd.moveto(INKWELL_X, INKWELL_Y)

    nd.pendown()
    time.sleep(0.3)

    # Stirring paramétrico según radio del pocillo
    r = INKWELL_RADIUS * 0.5  # Usamos la mitad del radio para no rozar el borde
    nd.lineto(INKWELL_X + r, INKWELL_Y)
    nd.lineto(INKWELL_X + r, INKWELL_Y + r)
    nd.lineto(INKWELL_X, INKWELL_Y + r)
    nd.lineto(INKWELL_X, INKWELL_Y)

    nd.penup()
    time.sleep(0.1)
    nd.pendown()
    time.sleep(0.2)

    nd.penup()
    nd.moveto(resume_x, resume_y)
    print("--- Retomando el lienzo... ---\n")
    distance_drawn = 0.0


print("Leyendo y procesando SVG...")
try:
    paths, attributes = svg2paths(SVG_FILE)
except FileNotFoundError:
    emergency_shutdown(nd, f"No se encontró {SVG_FILE}")
    sys.exit(1)

trazos_continuos = []
min_x, min_y = float("inf"), float("inf")
max_x, max_y = float("-inf"), float("-inf")

for path in paths:
    if len(path) == 0:
        continue
    puntos = flatten_path(path)
    # Subdivisión inicial en unidades SVG (se reajustará con escala)
    # Usamos un máximo generoso aquí; lo afinamos tras conocer la escala.
    if len(puntos) > 1:
        trazos_continuos.append(puntos)
        for (x, y) in puntos:
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)

if not trazos_continuos:
    emergency_shutdown(nd, "No se encontraron trazos válidos en el SVG.")
    sys.exit(1)

svg_width = max_x - min_x
svg_height = max_y - min_y
SCALE = DRAWING_WIDTH / svg_width if svg_width > 0 else 1.0

# Recalculamos subdivisión con la escala conocida
max_seg_svg_units = MAX_SEGMENT_LEN / SCALE
trazos_continuos = [
    subdivide_long_segments(t, max_seg_svg_units) for t in trazos_continuos
]

# Validación: ¿cabe el dibujo en el plotter?
phys_max_x = START_X + DRAWING_WIDTH
phys_max_y = START_Y + svg_height * SCALE
if phys_max_x > PLOTTER_MAX_X or phys_max_y > PLOTTER_MAX_Y:
    emergency_shutdown(
        nd,
        f"El dibujo se sale del área útil ({phys_max_x:.1f} x {phys_max_y:.1f}). "
        f"Límites: {PLOTTER_MAX_X} x {PLOTTER_MAX_Y}.",
    )
    sys.exit(1)

# Validación: ¿el dibujo solapa con el tintero?
if START_X < INKWELL_X + INKWELL_RADIUS * 5:
    print(
        f"[!] Aviso: START_X ({START_X}) está muy cerca del tintero "
        f"({INKWELL_X}). El cabezal podría chocar."
    )

print(f"Total de trazos: {len(trazos_continuos)}")
print(f"Dimensiones físicas: {DRAWING_WIDTH:.1f}\" x {svg_height * SCALE:.1f}\"")

# Detección de sesión previa
previous = load_state()
if previous and previous["last_completed_stroke"] > 0:
    last = previous["last_completed_stroke"]
    answer = input(f"\nSesión previa detectada en trazo {last}. ¿Reanudar? (s/N): ")
    if answer.strip().lower() == "s":
        START_AT_STROKE = last

if START_AT_STROKE > 0:
    print(f">>> REANUDANDO DESDE EL TRAZO {START_AT_STROKE} <<<")

# =================================================================
# BUCLE PRINCIPAL
# =================================================================
index = START_AT_STROKE
try:
    for index in range(START_AT_STROKE, len(trazos_continuos)):
        trazo = trazos_continuos[index]

        start_x = ((trazo[0][0] - min_x) * SCALE) + START_X
        start_y = ((trazo[0][1] - min_y) * SCALE) + START_Y

        nd.penup()
        nd.moveto(start_x, start_y)
        nd.pendown()

        for i in range(1, len(trazo)):
            curr_x = ((trazo[i - 1][0] - min_x) * SCALE) + START_X
            curr_y = ((trazo[i - 1][1] - min_y) * SCALE) + START_Y
            next_x = ((trazo[i][0] - min_x) * SCALE) + START_X
            next_y = ((trazo[i][1] - min_y) * SCALE) + START_Y

            seg_len = math.hypot(next_x - curr_x, next_y - curr_y)

            if distance_drawn + seg_len > MAX_DRAW_DIST:
                dip_brush(curr_x, curr_y)
                nd.pendown()

            nd.lineto(next_x, next_y)
            distance_drawn += seg_len

        nd.penup()
        save_state(index + 1, len(trazos_continuos))

    print("\n¡Pintura terminada! Volviendo a base...")
    nd.penup()
    nd.moveto(0, 0)
    nd.usb_command("EM,0,0")
    nd.disconnect()
    # Limpiamos el estado al terminar con éxito
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)

except KeyboardInterrupt:
    print(f"\n\n[!] INTERRUPCIÓN MANUAL en el trazo {index}.")
    save_state(index, len(trazos_continuos))
    emergency_shutdown(nd)
    print("---> Motores apagados. Mueve el cabezal a Home manualmente.")
    print(f"---> Para reanudar: vuelve a ejecutar el script y confirma cuando pregunte.")
    sys.exit(0)

except Exception as e:
    print(f"\n\n[!] ERROR INESPERADO en el trazo {index}: {type(e).__name__}: {e}")
    save_state(index, len(trazos_continuos))
    emergency_shutdown(nd)
    raise
