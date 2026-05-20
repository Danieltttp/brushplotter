"""Worker que ejecuta el bucle de pintura en un hilo separado.

Diseñado para no congelar la GUI: emite señales Qt en cada evento
importante (trazo terminado, recarga, error) que la ventana principal
escucha y refleja en pantalla.

La separación es estricta:
- La GUI nunca llama directamente al PlotterController.
- El worker lee la PaintingSession (estado compartido) y muta su
  estado interno (status de trazos, log de eventos).
- La GUI observa la session a través de las señales del worker.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

try:
    from PySide6.QtCore import QObject, QThread, Signal
except ImportError:
    # Fallback para entornos sin Qt (tests del core):
    # señales no-op con método .emit() para no romper el código.
    class QObject:
        pass

    class QThread:
        pass

    class _StubSignal:
        def __init__(self, *args, **kwargs):
            pass

        def emit(self, *args, **kwargs):
            pass

        def connect(self, *args, **kwargs):
            pass

    def Signal(*args, **kwargs):  # noqa: N802 (Qt naming)
        return _StubSignal()

from ..core.stroke_model import (
    PaintingSession,
    Point,
    Stroke,
    StrokeStatus,
)
from ..hardware.controller import PlotterController


class WorkerCommand(Enum):
    """Comandos que la GUI puede enviar al worker."""
    NONE = "none"
    PAUSE = "pause"
    STOP = "stop"
    RESUME = "resume"
    CONTINUE_AFTER_COLOR_CHANGE = "continue_color"


@dataclass
class DipPattern:
    """Patrón del ritual de recarga de pintura.

    Todos los parámetros en pulgadas y segundos.
    """
    dwell_seconds: float = 0.3
    stirring_radius: float = 0.04
    bob_count: int = 1
    bob_pause: float = 0.2


class PaintWorker(QObject):
    """Bucle de pintura ejecutado en su propio QThread.

    Señales:
        stroke_started(int):       índice del trazo que empieza
        stroke_finished(int):      índice del trazo terminado
        dip_started(str):          color_id del tintero al que va
        dip_finished():            recarga completada
        position_changed(float,float): nueva posición física del cabezal (pulgadas)
        progress_changed(float):   fracción [0,1] de progreso
        color_change_requested(str,str): old_color_id, new_color_id — espera confirmación
        paused():                  worker en pausa
        resumed():                 worker reanudado
        finished():                ejecución completa
        error(str):                error inesperado

    Uso típico desde la GUI:
        thread = QThread()
        worker = PaintWorker(session, controller)
        worker.moveToThread(thread)
        worker.stroke_finished.connect(canvas_view.mark_stroke_done)
        worker.color_change_requested.connect(show_color_change_dialog)
        thread.started.connect(worker.run)
        thread.start()
    """

    # Señales (se reemplazan por None en entornos sin Qt)
    stroke_started = Signal(int)
    stroke_finished = Signal(int)
    dip_started = Signal(str)
    dip_finished = Signal()
    position_changed = Signal(float, float)
    progress_changed = Signal(float)
    color_change_requested = Signal(str, str)
    paused = Signal()
    resumed = Signal()
    finished = Signal()
    error = Signal(str)

    def __init__(
        self,
        session: PaintingSession,
        controller: PlotterController,
        dip_pattern: Optional[DipPattern] = None,
        start_at_stroke: int = 0,
    ):
        super().__init__()
        self.session = session
        self.controller = controller
        self.dip_pattern = dip_pattern or DipPattern()
        self.start_at_stroke = start_at_stroke
        self._command = WorkerCommand.NONE
        self._distance_drawn = 0.0
        self._current_color_id: Optional[str] = None
        self._color_change_acknowledged = False

    # ------------------------------------------------------------------
    # API pública: la GUI llama estos métodos desde el hilo principal.
    # Son thread-safe porque solo escriben un enum atómico.
    # ------------------------------------------------------------------
    def request_pause(self):
        self._command = WorkerCommand.PAUSE

    def request_stop(self):
        self._command = WorkerCommand.STOP

    def request_resume(self):
        self._command = WorkerCommand.RESUME

    def acknowledge_color_change(self):
        """Llamado por la GUI tras confirmar que el usuario ya cambió
        de tintero / limpió el pincel."""
        self._color_change_acknowledged = True

    # ------------------------------------------------------------------
    # Bucle principal (ejecutado en el QThread del worker)
    # ------------------------------------------------------------------
    def run(self):
        try:
            self._run_unsafe()
        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}")
            self._emergency_shutdown()

    def _run_unsafe(self):
        if not self.controller.connect():
            self.error.emit("No se pudo conectar al plotter.")
            return

        self.controller.apply_profile(self.session.material_profile)
        self.controller.enable_motors()
        self.session.started_at = time.time()
        self.session.log_event("session_started")

        total = len(self.session.strokes)
        for idx in range(self.start_at_stroke, total):
            stroke = self.session.strokes[idx]

            # --- Atención a comandos antes de cada trazo ---
            if self._check_stop():
                return
            self._wait_if_paused()

            # Trazos sin color asignado se saltan (no se pintan)
            if stroke.color_id is None:
                stroke.status = StrokeStatus.SKIPPED
                continue

            # --- Cambio de color: pausa para que el usuario limpie ---
            if stroke.color_id != self._current_color_id:
                old = self._current_color_id
                self._current_color_id = stroke.color_id
                self.session.log_event(
                    "color_change",
                    from_color=old,
                    to_color=stroke.color_id,
                )
                self.color_change_requested.emit(old or "", stroke.color_id)
                self._color_change_acknowledged = False
                while not self._color_change_acknowledged:
                    if self._check_stop():
                        return
                    time.sleep(0.05)
                self._distance_drawn = 0.0  # tras limpiar, pincel vacío

            # --- Pintar el trazo ---
            self._paint_stroke(idx, stroke)

            # --- Progreso ---
            stroke.status = StrokeStatus.DONE
            self.session.log_event("stroke_done", index=idx)
            self.stroke_finished.emit(idx)
            self.progress_changed.emit((idx + 1) / total)

        # --- Cierre limpio ---
        self.controller.pen_up()
        self.controller.move_to(Point(0, 0))
        self.controller.disable_motors()
        self.controller.disconnect()
        self.session.completed_at = time.time()
        self.session.log_event("session_completed")
        self.finished.emit()

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------
    def _paint_stroke(self, idx: int, stroke: Stroke):
        """Pinta un trazo, con recargas intermedias si hace falta."""
        self.stroke_started.emit(idx)
        stroke.status = StrokeStatus.DRAWING

        start_phys = self.session.svg_to_physical(*stroke.points[0])
        self.controller.pen_up()
        self.controller.move_to(start_phys)
        self.position_changed.emit(start_phys.x, start_phys.y)
        self.controller.pen_down()

        max_dist = self.session.material_profile.max_draw_distance_inches

        for i in range(1, len(stroke.points)):
            if self._check_stop():
                return
            self._wait_if_paused()

            prev = self.session.svg_to_physical(*stroke.points[i - 1])
            curr = self.session.svg_to_physical(*stroke.points[i])
            seg_len = math.hypot(curr.x - prev.x, curr.y - prev.y)

            if self._distance_drawn + seg_len > max_dist:
                self._dip_at_current_color(resume_at=curr)
                self.controller.pen_down()

            self.controller.line_to(curr)
            self.position_changed.emit(curr.x, curr.y)
            self._distance_drawn += seg_len

        self.controller.pen_up()

    def _dip_at_current_color(self, resume_at: Point):
        """Ritual de recarga en el tintero del color activo."""
        color = self.session.colors[self._current_color_id]
        if not color.is_calibrated:
            self.error.emit(
                f"Color '{color.name}' no tiene tintero calibrado."
            )
            raise RuntimeError(f"Tintero no calibrado: {color.name}")

        self.dip_started.emit(self._current_color_id)
        self.session.log_event("dip", color_id=self._current_color_id)

        ink = color.inkwell_position
        p = self.dip_pattern

        self.controller.pen_up()
        self.controller.move_to(ink)
        self.controller.pen_down()
        time.sleep(p.dwell_seconds)

        # Stirring
        r = p.stirring_radius
        self.controller.line_to(Point(ink.x + r, ink.y))
        self.controller.line_to(Point(ink.x + r, ink.y + r))
        self.controller.line_to(Point(ink.x, ink.y + r))
        self.controller.line_to(Point(ink.x, ink.y))

        # Bobbing
        for _ in range(p.bob_count):
            self.controller.pen_up()
            time.sleep(0.1)
            self.controller.pen_down()
            time.sleep(p.bob_pause)

        # Vuelta al lienzo
        self.controller.pen_up()
        self.controller.move_to(resume_at)
        self._distance_drawn = 0.0
        self.dip_finished.emit()

    def _check_stop(self) -> bool:
        if self._command == WorkerCommand.STOP:
            self.session.log_event("stopped_by_user")
            self._emergency_shutdown()
            self.finished.emit()
            return True
        return False

    def _wait_if_paused(self):
        if self._command == WorkerCommand.PAUSE:
            self.controller.pen_up()
            self.session.log_event("paused")
            self.paused.emit()
            while self._command == WorkerCommand.PAUSE:
                time.sleep(0.1)
            self.session.log_event("resumed")
            self.resumed.emit()

    def _emergency_shutdown(self):
        try:
            self.controller.pen_up()
            self.controller.disable_motors()
            self.controller.disconnect()
        except Exception:
            pass
