"""Modelo de datos del proyecto.

Sin dependencias de Qt ni de hardware. Testeable de forma aislada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# Conversión interna: la GUI muestra mm, el plotter usa pulgadas.
MM_PER_INCH = 25.4


def mm_to_inches(mm: float) -> float:
    return mm / MM_PER_INCH


def inches_to_mm(inches: float) -> float:
    return inches * MM_PER_INCH


class StrokeStatus(Enum):
    PENDING = "pending"
    DRAWING = "drawing"
    DONE = "done"
    SKIPPED = "skipped"


@dataclass
class Point:
    """Punto en coordenadas físicas (pulgadas, sistema del plotter)."""
    x: float
    y: float


@dataclass
class InkColor:
    """Un color asignable a trazos, vinculado a una posición de tintero.

    name: nombre legible ('Azul ultramar')
    hex: color para preview en pantalla ('#185FA5')
    inkwell_position: posición física del tintero (None = sin asignar)
    """
    name: str
    hex: str
    inkwell_position: Optional[Point] = None

    @property
    def is_calibrated(self) -> bool:
        return self.inkwell_position is not None


@dataclass
class Stroke:
    """Un trazo continuo aplanado a polilínea.

    points: lista de puntos en coordenadas SVG originales (sin escalar).
    El escalado a coordenadas físicas se aplica al ejecutar.
    color_id: id del InkColor asignado (None = sin color, no se pinta).
    source_layer: capa SVG de origen (si la había), útil para asignación
    automática.
    source_stroke_attr: valor del atributo stroke="..." del SVG.
    """
    points: list[tuple[float, float]]
    color_id: Optional[str] = None
    source_layer: Optional[str] = None
    source_stroke_attr: Optional[str] = None
    status: StrokeStatus = StrokeStatus.PENDING

    @property
    def length_svg_units(self) -> float:
        """Longitud total del trazo en unidades SVG."""
        import math
        total = 0.0
        for i in range(1, len(self.points)):
            x0, y0 = self.points[i - 1]
            x1, y1 = self.points[i]
            total += math.hypot(x1 - x0, y1 - y0)
        return total


@dataclass
class MaterialProfile:
    """Perfil de material que define cómo se comporta el pincel.

    Las velocidades y posiciones son las que acepta la API NextDraw.
    """
    name: str
    speed_pendown: int = 5
    speed_penup: int = 40
    pen_pos_down: int = 40
    pen_pos_up: int = 70
    pen_rate_lower: int = 20
    pen_rate_raise: int = 50
    # Específicos del ritual de recarga:
    max_draw_distance_inches: float = 5.0
    dip_dwell_seconds: float = 0.3
    dip_stirring_enabled: bool = True
    dip_bob_count: int = 1


DEFAULT_PROFILES = {
    "acuarela": MaterialProfile(
        name="Acuarela",
        speed_pendown=5,
        max_draw_distance_inches=4.0,
        dip_dwell_seconds=0.5,
    ),
    "acrilico_diluido": MaterialProfile(
        name="Acrílico diluido",
        speed_pendown=4,
        pen_pos_down=35,  # Más presión, el acrílico es más viscoso
        max_draw_distance_inches=3.0,
        dip_dwell_seconds=0.8,
        dip_bob_count=2,
    ),
    "tinta_china": MaterialProfile(
        name="Tinta china",
        speed_pendown=8,
        max_draw_distance_inches=8.0,
        dip_dwell_seconds=0.2,
    ),
}


@dataclass
class CanvasGeometry:
    """Configuración del soporte físico y posición del dibujo.

    Todo en pulgadas (unidades nativas del plotter).
    Defaults para NextDraw 2234 (A1, 34.02 x 23.39 pulgadas).
    """
    start_x: float = 3.0
    start_y: float = 2.0
    drawing_width: float = 8.0  # Alto se deriva del aspect ratio del SVG
    plotter_max_x: float = 34.02
    plotter_max_y: float = 23.39


@dataclass
class PaintingSession:
    """Estado completo de una sesión de pintura. Serializable a JSON.

    Es la fuente de verdad: la GUI lo observa, el worker lo modifica,
    persistence.py lo guarda y restaura.
    """
    svg_file_path: str
    strokes: list[Stroke] = field(default_factory=list)
    colors: dict[str, InkColor] = field(default_factory=dict)
    material_profile: MaterialProfile = field(
        default_factory=lambda: DEFAULT_PROFILES["acuarela"]
    )
    canvas: CanvasGeometry = field(default_factory=CanvasGeometry)

    # Bounding box del SVG (calculado al cargar)
    svg_min_x: float = 0.0
    svg_min_y: float = 0.0
    svg_max_x: float = 0.0
    svg_max_y: float = 0.0

    # Progreso
    current_stroke_index: int = 0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    # Log de eventos para documentación de la obra
    event_log: list[dict] = field(default_factory=list)

    @property
    def scale(self) -> float:
        """Factor para convertir unidades SVG a pulgadas físicas."""
        svg_width = self.svg_max_x - self.svg_min_x
        if svg_width <= 0:
            return 1.0
        return self.canvas.drawing_width / svg_width

    @property
    def physical_height(self) -> float:
        return (self.svg_max_y - self.svg_min_y) * self.scale

    @property
    def progress_fraction(self) -> float:
        if not self.strokes:
            return 0.0
        done = sum(1 for s in self.strokes if s.status == StrokeStatus.DONE)
        return done / len(self.strokes)

    @property
    def unassigned_stroke_count(self) -> int:
        """Trazos sin color asignado (no se pintarán)."""
        return sum(1 for s in self.strokes if s.color_id is None)

    @property
    def uncalibrated_colors(self) -> list[InkColor]:
        """Colores asignados a trazos pero sin tintero calibrado."""
        used_ids = {s.color_id for s in self.strokes if s.color_id}
        return [
            self.colors[cid]
            for cid in used_ids
            if cid in self.colors and not self.colors[cid].is_calibrated
        ]

    def svg_to_physical(self, x: float, y: float) -> Point:
        """Convierte un punto en unidades SVG a pulgadas físicas."""
        phys_x = (x - self.svg_min_x) * self.scale + self.canvas.start_x
        phys_y = (y - self.svg_min_y) * self.scale + self.canvas.start_y
        return Point(phys_x, phys_y)

    def log_event(self, event_type: str, **kwargs):
        """Añade un evento al log con timestamp."""
        import time
        entry = {"timestamp": time.time(), "type": event_type, **kwargs}
        self.event_log.append(entry)
