"""Vista del lienzo: previsualización del SVG con capas separadas para
trazos pendientes, en curso y completados.

Recibe el PaintingSession y dibuja cada Stroke como un QGraphicsPathItem.
Las señales del PaintWorker actualizan el estado visual sin redibujar todo.

Convención: el SVG se renderiza con coordenadas físicas (mm en pantalla,
escalado al área visible). El eje Y se invierte para que coincida con la
convención visual (Y hacia abajo en SVG = Y hacia abajo en pantalla, pero
también queremos que coincida espacialmente con el lienzo físico).
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
)

from ..core.stroke_model import (
    InkColor,
    PaintingSession,
    Stroke,
    StrokeStatus,
    inches_to_mm,
)


# Colores de estado para trazos sin color asignado
PENDING_UNASSIGNED_COLOR = QColor(180, 180, 180, 100)  # gris claro
PENDING_ASSIGNED_OPACITY = 0.35  # trazos con color, todavía no pintados
DONE_OPACITY = 1.0
DRAWING_OPACITY = 0.7

# Color del cursor de posición del cabezal
HEAD_CURSOR_COLOR = QColor("#222222")


class CanvasView(QGraphicsView):
    """Vista del lienzo con preview del SVG y estado en tiempo real.

    El sistema de coordenadas interno es milímetros físicos (lo que se
    renderiza en pantalla). La conversión desde SVG la hace
    PaintingSession.svg_to_physical (que devuelve pulgadas), y
    aplicamos *25.4 para pasar a mm.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        # Y hacia abajo (convención de pantalla y de SVG)
        # Si quisiéramos Y hacia arriba (convención física), usaríamos:
        # self.scale(1, -1)

        self._session: PaintingSession | None = None
        self._stroke_items: list[QGraphicsPathItem] = []
        self._head_cursor: QGraphicsEllipseItem | None = None
        self._canvas_rect: QGraphicsRectItem | None = None

    def load_session(self, session: PaintingSession):
        """Renderiza un PaintingSession en la escena."""
        self._scene.clear()
        self._stroke_items = []
        self._head_cursor = None
        self._session = session

        # 1. Rectángulo del área útil del plotter (referencia visual)
        plotter_w_mm = inches_to_mm(session.canvas.plotter_max_x)
        plotter_h_mm = inches_to_mm(session.canvas.plotter_max_y)
        self._canvas_rect = self._scene.addRect(
            0,
            0,
            plotter_w_mm,
            plotter_h_mm,
            QPen(QColor(200, 200, 200), 1),
            QBrush(QColor(250, 250, 248)),
        )
        self._canvas_rect.setZValue(-10)

        # Etiquetas de orientación física del plotter
        from PySide6.QtWidgets import QGraphicsSimpleTextItem
        from PySide6.QtGui import QFont
        font = QFont("Menlo", 9)
        # Home en esquina sup. izq.
        home_label = QGraphicsSimpleTextItem("⌂ Home (0,0)")
        home_label.setFont(font)
        home_label.setBrush(QColor(120, 120, 120))
        home_label.setPos(2, -14)
        self._scene.addItem(home_label)
        # Eje X (lado largo del plotter)
        x_label = QGraphicsSimpleTextItem(f"X — {inches_to_mm(session.canvas.plotter_max_x)/10:.0f} cm →")
        x_label.setFont(font)
        x_label.setBrush(QColor(120, 120, 120))
        x_label.setPos(plotter_w_mm - 80, -14)
        self._scene.addItem(x_label)
        # Eje Y (lado corto)
        y_label = QGraphicsSimpleTextItem(f"↓ Y — {inches_to_mm(session.canvas.plotter_max_y)/10:.0f} cm")
        y_label.setFont(font)
        y_label.setBrush(QColor(120, 120, 120))
        y_label.setPos(-50, plotter_h_mm / 2)
        self._scene.addItem(y_label)

        # 2. Rectángulo del área de dibujo (dentro del plotter)
        # Considera la rotación: si está rotado 90°, el dibujo en pantalla
        # ocupa el alto donde antes estaba el ancho y viceversa.
        dx = inches_to_mm(session.canvas.start_x)
        dy = inches_to_mm(session.canvas.start_y)
        if session.canvas.rotation_degrees == 90:
            dw = inches_to_mm(session.physical_height)
            dh = inches_to_mm(session.physical_width)
        else:
            dw = inches_to_mm(session.physical_width)
            dh = inches_to_mm(session.physical_height)
        drawing_rect = self._scene.addRect(
            dx, dy, dw, dh,
            QPen(QColor(180, 180, 200), 0.5, Qt.PenStyle.DashLine),
            QBrush(QColor(255, 255, 255)),
        )
        drawing_rect.setZValue(-9)

        # 3. Posición de los tinteros (círculos pequeños)
        for cid, color in session.colors.items():
            if not color.is_calibrated:
                continue
            ink = color.inkwell_position
            ix = inches_to_mm(ink.x)
            iy = inches_to_mm(ink.y)
            r = 4.0  # radio del marcador en mm
            qc = QColor(color.hex)
            marker = self._scene.addEllipse(
                ix - r,
                iy - r,
                r * 2,
                r * 2,
                QPen(qc, 1.0),
                QBrush(QColor(qc.red(), qc.green(), qc.blue(), 80)),
            )
            marker.setZValue(-5)
            marker.setToolTip(f"Tintero: {color.name}")

        # 3b. Estación de agua (círculo azul claro, mayor que tinteros)
        if session.water_station.is_calibrated:
            wp = session.water_station.position
            wx = inches_to_mm(wp.x)
            wy = inches_to_mm(wp.y)
            wr = 6.0  # más grande que un tintero (un vaso de agua)
            water_color = QColor("#5b9bd5")
            water_marker = self._scene.addEllipse(
                wx - wr, wy - wr, wr * 2, wr * 2,
                QPen(water_color, 1.2),
                QBrush(QColor(water_color.red(), water_color.green(), water_color.blue(), 60)),
            )
            water_marker.setZValue(-5)
            water_marker.setToolTip("Estación de agua")
            # Etiqueta "💧" centrada
            from PySide6.QtWidgets import QGraphicsSimpleTextItem
            water_label = QGraphicsSimpleTextItem("💧")
            water_label.setPos(wx - 4, wy - 8)
            water_label.setZValue(-4)
            self._scene.addItem(water_label)

        # 4. Los trazos
        for stroke in session.strokes:
            item = self._make_stroke_item(stroke, session)
            self._scene.addItem(item)
            self._stroke_items.append(item)

        # 5. Cursor de posición del cabezal
        self._head_cursor = self._scene.addEllipse(
            -2, -2, 4, 4,
            QPen(HEAD_CURSOR_COLOR, 1.5),
            QBrush(QColor(255, 255, 255, 0)),
        )
        self._head_cursor.setZValue(100)
        self._head_cursor.setVisible(False)

        # Ajustar zoom para mostrar todo el plotter
        self._scene.setSceneRect(
            -10, -10, plotter_w_mm + 20, plotter_h_mm + 20
        )
        self.fitInView(
            self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
        )

    def _make_stroke_item(
        self, stroke: Stroke, session: PaintingSession
    ) -> QGraphicsPathItem:
        """Construye un QGraphicsPathItem a partir de un Stroke."""
        path = QPainterPath()
        first = True
        for x_svg, y_svg in stroke.points:
            phys = session.svg_to_physical(x_svg, y_svg)
            px = inches_to_mm(phys.x)
            py = inches_to_mm(phys.y)
            if first:
                path.moveTo(px, py)
                first = False
            else:
                path.lineTo(px, py)

        item = QGraphicsPathItem(path)
        pen = self._pen_for_stroke(stroke, session)
        item.setPen(pen)
        return item

    def _pen_for_stroke(
        self, stroke: Stroke, session: PaintingSession
    ) -> QPen:
        """Calcula el QPen apropiado según estado y color asignado."""
        if stroke.color_id is None:
            # Sin color: gris discontinuo, no se va a pintar
            pen = QPen(PENDING_UNASSIGNED_COLOR, 0.8)
            pen.setStyle(Qt.PenStyle.DashLine)
            return pen

        color: InkColor = session.colors[stroke.color_id]
        qc = QColor(color.hex)

        if stroke.status == StrokeStatus.DONE:
            qc.setAlphaF(DONE_OPACITY)
        elif stroke.status == StrokeStatus.DRAWING:
            qc.setAlphaF(DRAWING_OPACITY)
        else:  # PENDING
            qc.setAlphaF(PENDING_ASSIGNED_OPACITY)

        pen = QPen(qc, 0.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        return pen

    # ----------------------------------------------------------
    # Slots conectados a las señales del PaintWorker
    # ----------------------------------------------------------
    def mark_stroke_drawing(self, index: int):
        """El worker ha empezado a pintar este trazo."""
        if 0 <= index < len(self._stroke_items) and self._session:
            stroke = self._session.strokes[index]
            stroke.status = StrokeStatus.DRAWING
            self._stroke_items[index].setPen(
                self._pen_for_stroke(stroke, self._session)
            )

    def mark_stroke_done(self, index: int):
        """El worker ha completado este trazo."""
        if 0 <= index < len(self._stroke_items) and self._session:
            stroke = self._session.strokes[index]
            stroke.status = StrokeStatus.DONE
            self._stroke_items[index].setPen(
                self._pen_for_stroke(stroke, self._session)
            )

    def update_head_position(self, x_inches: float, y_inches: float):
        """Actualiza la posición del cursor del cabezal."""
        if self._head_cursor is None:
            return
        x_mm = inches_to_mm(x_inches)
        y_mm = inches_to_mm(y_inches)
        self._head_cursor.setRect(x_mm - 2, y_mm - 2, 4, 4)
        self._head_cursor.setVisible(True)

    def wheelEvent(self, event):
        """Zoom con scroll de rueda."""
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)
