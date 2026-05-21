"""Carga y aplanado de archivos SVG.

A diferencia del script original, este módulo:
- Aplana correctamente curvas Bézier y Arcs.
- Extrae información de capa (atributo inkscape:label, id de <g>) y
  atributo stroke para asignación automática de color.
- Devuelve un objeto PaintingSession listo para usar.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

from svgpathtools import (
    Arc,
    CubicBezier,
    Line,
    QuadraticBezier,
    svg2paths2,
)

from .stroke_model import (
    CanvasGeometry,
    InkColor,
    PaintingSession,
    Stroke,
)
from .units import mm_to_inches, cm_to_inches


BEZIER_SAMPLES = 20
MAX_SEGMENT_LEN_SVG_RATIO = 0.005  # 0.5% del ancho del SVG por segmento


# Conversión de unidades SVG a pulgadas (96 DPI estándar)
SVG_USER_UNITS_PER_INCH = 96.0


def _parse_svg_dimension(value: str) -> float:
    """Parsea una dimensión SVG (con o sin unidades) a pulgadas.

    Acepta: '210mm', '8.27in', '297pt', '1024px', '595' (sin unidad → px).
    Devuelve 0 si no se puede parsear.
    """
    if not value:
        return 0.0
    value = value.strip().lower()
    # Separar número y unidad
    import re
    match = re.match(r"^([0-9.+\-eE]+)\s*([a-z%]*)$", value)
    if not match:
        return 0.0
    try:
        num = float(match.group(1))
    except ValueError:
        return 0.0
    unit = match.group(2)

    if unit == "mm":
        return mm_to_inches(num)
    if unit == "cm":
        return cm_to_inches(num)
    if unit == "in":
        return num
    if unit == "pt":
        return num / 72.0  # 72 pt = 1 in
    if unit == "pc":
        return num / 6.0   # 6 pc = 1 in
    if unit in ("", "px"):
        return num / SVG_USER_UNITS_PER_INCH
    if unit == "%":
        return 0.0  # No se puede resolver sin contexto
    return num / SVG_USER_UNITS_PER_INCH  # fallback px


def flatten_path(path, samples: int = BEZIER_SAMPLES) -> list[tuple[float, float]]:
    """Convierte un path en lista de puntos, muestreando curvas."""
    points: list[tuple[float, float]] = []
    for segment in path:
        if not points:
            points.append((segment.start.real, segment.start.imag))
        if isinstance(segment, Line):
            points.append((segment.end.real, segment.end.imag))
        elif isinstance(segment, (CubicBezier, QuadraticBezier, Arc)):
            for i in range(1, samples + 1):
                t = i / samples
                pt = segment.point(t)
                points.append((pt.real, pt.imag))
        else:
            points.append((segment.end.real, segment.end.imag))
    return points


def subdivide_long_segments(
    points: list[tuple[float, float]], max_len: float
) -> list[tuple[float, float]]:
    """Inserta puntos intermedios en segmentos que excedan max_len."""
    if len(points) < 2:
        return points
    result = [points[0]]
    for i in range(1, len(points)):
        x0, y0 = result[-1]
        x1, y1 = points[i]
        seg_len = math.hypot(x1 - x0, y1 - y0)
        if seg_len > max_len:
            n_sub = int(math.ceil(seg_len / max_len))
            for k in range(1, n_sub + 1):
                t = k / n_sub
                result.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
        else:
            result.append((x1, y1))
    return result


def _extract_layer_info(svg_path: str) -> dict[str, str]:
    """Mapea id de path a label de capa Inkscape padre.

    svgpathtools no expone la jerarquía de <g>, así que parseamos el XML
    aparte para extraer la capa de cada path.
    """
    ns = {
        "svg": "http://www.w3.org/2000/svg",
        "inkscape": "http://www.inkscape.org/namespaces/inkscape",
    }
    tree = ET.parse(svg_path)
    root = tree.getroot()
    path_to_layer: dict[str, str] = {}

    def walk(element, current_layer: Optional[str]):
        tag = element.tag.split("}")[-1]
        if tag == "g":
            label = element.get(f"{{{ns['inkscape']}}}label") or element.get("id")
            if label:
                current_layer = label
        if tag == "path":
            pid = element.get("id")
            if pid and current_layer:
                path_to_layer[pid] = current_layer
        for child in element:
            walk(child, current_layer)

    walk(root, None)
    return path_to_layer


def load_svg(
    svg_path: str | Path,
    canvas: Optional[CanvasGeometry] = None,
) -> PaintingSession:
    """Carga un SVG y devuelve un PaintingSession listo para configurar.

    Asignación automática de color:
    - Si el path tiene atributo stroke="#RRGGBB", se crea/reutiliza un
      InkColor con ese hex.
    - Si está dentro de una capa Inkscape, queda registrado en
      source_layer para que la GUI permita asignar por capa.
    """
    svg_path = str(svg_path)
    paths, attributes, svg_attr = svg2paths2(svg_path)
    layer_map = _extract_layer_info(svg_path)

    session = PaintingSession(
        svg_file_path=svg_path,
        canvas=canvas or CanvasGeometry(),
    )

    # Extraer dimensiones nativas del documento SVG (atributos width/height)
    native_w = _parse_svg_dimension(svg_attr.get("width", ""))
    native_h = _parse_svg_dimension(svg_attr.get("height", ""))
    session.svg_native_width_inches = native_w
    session.svg_native_height_inches = native_h

    # Extraer viewBox: "min-x min-y width height"
    # Es lo que define el sistema de coordenadas del SVG, no el bounding
    # box de los trazos. Usarlo asegura que el lienzo declarado por el
    # artista (con sus márgenes) se respeta.
    viewbox = svg_attr.get("viewBox") or svg_attr.get("viewbox", "")
    viewbox_min_x = 0.0
    viewbox_min_y = 0.0
    viewbox_width = 0.0
    viewbox_height = 0.0
    if viewbox:
        try:
            parts = viewbox.replace(",", " ").split()
            if len(parts) == 4:
                viewbox_min_x = float(parts[0])
                viewbox_min_y = float(parts[1])
                viewbox_width = float(parts[2])
                viewbox_height = float(parts[3])
        except (ValueError, IndexError):
            pass

    # Bounding box
    min_x, min_y = float("inf"), float("inf")
    max_x, max_y = float("-inf"), float("-inf")

    strokes: list[Stroke] = []
    color_by_hex: dict[str, str] = {}

    for path, attr in zip(paths, attributes):
        if len(path) == 0:
            continue
        points = flatten_path(path)
        if len(points) < 2:
            continue

        stroke_attr = attr.get("stroke")
        layer = layer_map.get(attr.get("id", ""))

        # Asignación automática por stroke.
        # Solo descartamos "none" (sin trazo). El negro se trata como
        # color válido — el usuario puede tener un tintero de negro.
        color_id: Optional[str] = None
        if stroke_attr and stroke_attr.lower() != "none":
            normalized = stroke_attr.lower()
            if normalized not in color_by_hex:
                color_id = f"auto_{len(color_by_hex)}"
                color_by_hex[normalized] = color_id
                session.colors[color_id] = InkColor(
                    name=f"Color {len(color_by_hex)} ({normalized})",
                    hex=normalized,
                )
            else:
                color_id = color_by_hex[normalized]

        stroke = Stroke(
            points=points,
            color_id=color_id,
            source_layer=layer,
            source_stroke_attr=stroke_attr,
        )
        strokes.append(stroke)

        for (x, y) in points:
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)

    if not strokes:
        raise ValueError(f"No se encontraron trazos válidos en {svg_path}")

    # Fallback: si ningún path tenía atributo stroke, creamos un color
    # por defecto y se lo asignamos a todos.
    if not session.colors:
        default_id = "default"
        # Usamos el nombre del archivo (sin extensión) como nombre del color
        svg_name = Path(svg_path).stem
        session.colors[default_id] = InkColor(
            name=f"Único ({svg_name})",
            hex="#222222",
        )
        for s in strokes:
            s.color_id = default_id

    session.strokes = strokes

    # El sistema de coordenadas del SVG es el viewBox (si está declarado),
    # NO el bounding box de los trazos. Así respetamos los márgenes que
    # el artista dejó intencionalmente en el lienzo.
    if viewbox_width > 0 and viewbox_height > 0:
        session.svg_min_x = viewbox_min_x
        session.svg_min_y = viewbox_min_y
        session.svg_max_x = viewbox_min_x + viewbox_width
        session.svg_max_y = viewbox_min_y + viewbox_height
    else:
        # Fallback: sin viewBox, usamos el bounding box de los trazos
        session.svg_min_x = min_x
        session.svg_min_y = min_y
        session.svg_max_x = max_x
        session.svg_max_y = max_y

    # Si el SVG no declaró width/height nativos, deducirlos del viewBox
    # asumiendo 96 DPI estándar.
    if session.svg_native_width_inches <= 0:
        ref_w = viewbox_width if viewbox_width > 0 else (max_x - min_x)
        session.svg_native_width_inches = ref_w / SVG_USER_UNITS_PER_INCH
    if session.svg_native_height_inches <= 0:
        ref_h = viewbox_height if viewbox_height > 0 else (max_y - min_y)
        session.svg_native_height_inches = ref_h / SVG_USER_UNITS_PER_INCH

    # Subdivisión post-bounding-box: usamos un ratio del ancho del SVG
    # para que segmentos muy largos se troceen sin depender de escala.
    svg_width = max_x - min_x
    max_seg = svg_width * MAX_SEGMENT_LEN_SVG_RATIO
    for s in session.strokes:
        s.points = subdivide_long_segments(s.points, max_seg)

    return session


def assign_colors_by_layer(
    session: PaintingSession,
    layer_to_color_id: dict[str, str],
) -> int:
    """Reasigna color_id de cada stroke según su capa.

    Devuelve el número de trazos modificados.
    """
    count = 0
    for stroke in session.strokes:
        if stroke.source_layer in layer_to_color_id:
            new_id = layer_to_color_id[stroke.source_layer]
            if stroke.color_id != new_id:
                stroke.color_id = new_id
                count += 1
    return count
