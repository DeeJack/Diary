"""Graphics item for rendering stroke elements using QGraphicsItem architecture"""

from typing import cast, override

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget

from diary.config import settings
from diary.models.elements.stroke import Stroke
from diary.models.point import Point

from .base_graphics_item import BaseGraphicsItem


class StrokeGraphicsItem(BaseGraphicsItem):
    """Graphics item for rendering stroke elements with smooth curves and pressure sensitivity"""

    def __init__(self, stroke: Stroke, parent: QGraphicsItem | None = None):
        super().__init__(stroke, parent)
        self._stroke_path: QPainterPath | None = None
        self._pen: QPen | None = None

        # Configure item flags for strokes
        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False
        )  # Strokes shouldn't be movable

    @property
    def stroke(self) -> Stroke:
        """Get the stroke element"""
        return cast(Stroke, self._element)

    @override
    def _calculate_bounding_rect(self) -> QRectF:
        """Calculate the bounding rectangle including stroke thickness"""
        if not self.stroke.points:
            return QRectF()

        # Find the extremities of all points
        min_x = min(point.x for point in self.stroke.points)
        max_x = max(point.x for point in self.stroke.points)
        min_y = min(point.y for point in self.stroke.points)
        max_y = max(point.y for point in self.stroke.points)

        # Add margin for stroke thickness
        margin = self.stroke.thickness / 2.0 + 2.0  # Extra 2px for antialiasing

        return QRectF(
            min_x - margin,
            min_y - margin,
            (max_x - min_x) + 2 * margin,
            (max_y - min_y) + 2 * margin,
        )

    @override
    def paint(
        self,
        painter: QPainter | None,
        option: QStyleOptionGraphicsItem | None,
        widget: QWidget | None = None,
    ) -> None:
        """Paint the stroke with high-quality antialiasing and smooth curves"""
        if not self.stroke.points or not painter:
            return

        # Configure painter for high-quality rendering
        self.configure_painter_quality(painter)

        # Draw selection highlight if selected
        if self.isSelected():
            self._draw_selection_highlight(painter)

        if len(self.stroke.points) == 1:
            self._paint_single_point(painter)
        else:
            self._paint_stroke_path(painter)

    def _draw_selection_highlight(self, painter: QPainter) -> None:
        """Draw selection highlight around the stroke"""
        highlight_pen = QPen(QColor(0, 120, 255, 128))  # Semi-transparent blue
        highlight_pen.setWidth(int(self.stroke.thickness + 4))
        highlight_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        highlight_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

        painter.setPen(highlight_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        path = self._get_stroke_path()
        if path:
            painter.drawPath(path)

    def _paint_single_point(self, painter: QPainter) -> None:
        """Paint a single point as a dot"""
        point = self.stroke.points[0]

        pen = self._create_pen_for_pressure(point.pressure)
        painter.setPen(pen)
        painter.drawPoint(QPointF(point.x, point.y))

    def _paint_stroke_path(self, painter: QPainter) -> None:
        """Paint the stroke as a smooth path with optional pressure sensitivity"""
        if settings.USE_PRESSURE and self._has_varying_pressure():
            self._paint_variable_width_stroke(painter)
        else:
            self._paint_uniform_width_stroke(painter)

    def _paint_uniform_width_stroke(self, painter: QPainter) -> None:
        """Paint stroke with uniform width"""
        # Calculate average pressure for uniform width
        avg_pressure = sum(p.pressure for p in self.stroke.points) / len(
            self.stroke.points
        )

        pen = self._create_pen_for_pressure(avg_pressure)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        path = self._get_stroke_path()
        if path:
            painter.drawPath(path)

    def _paint_variable_width_stroke(self, painter: QPainter) -> None:
        """Paint stroke with variable width based on pressure"""
        points = self.stroke.points

        # Draw segments with varying width
        for i in range(len(points) - 1):
            p1 = points[i]
            p2 = points[i + 1]

            # Calculate width for this segment
            segment_pressure = (p1.pressure + p2.pressure) / 2.0

            pen = self._create_pen_for_pressure(segment_pressure)
            painter.setPen(pen)

            # Create smooth segment path
            segment_path = QPainterPath()
            segment_path.moveTo(p1.x, p1.y)

            if i < len(points) - 2:
                # Use quadratic curve to next point
                p3 = points[i + 2]
                mid_x = (p2.x + p3.x) / 2.0
                mid_y = (p2.y + p3.y) / 2.0
                segment_path.quadTo(p2.x, p2.y, mid_x, mid_y)
            else:
                # Last segment - draw line to end
                segment_path.lineTo(p2.x, p2.y)

            painter.drawPath(segment_path)

    def _get_stroke_path(self) -> QPainterPath:
        """Get or create the cached stroke path"""
        if self._stroke_path is None:
            self._stroke_path = self._create_stroke_path()
        return self._stroke_path

    def _create_stroke_path(self) -> QPainterPath:
        """Create a smooth path through all stroke points"""
        if not self.stroke.points:
            return QPainterPath()

        points = self.stroke.points
        path = QPainterPath()

        # Start the path at the first point
        path.moveTo(points[0].x, points[0].y)

        if len(points) == 2:
            # Simple line for two points
            path.lineTo(points[1].x, points[1].y)
        elif len(points) > 2:
            # Create smooth curves using quadratic Bezier curves
            self._build_smooth_curve_path(points, path)

        return path

    def _build_smooth_curve_path(self, points: list[Point], path: QPainterPath) -> None:
        """Build a smooth curve path through all points using Bezier curves"""
        # Draw line to first control point
        path.lineTo(points[1].x, points[1].y)

        # Create smooth curves through the middle points
        for i in range(1, len(points) - 2):
            p2 = points[i + 1]
            p3 = points[i + 2]

            # Use the current point as control and midpoint to next as end
            mid_x = (p2.x + p3.x) / 2.0
            mid_y = (p2.y + p3.y) / 2.0

            path.quadTo(p2.x, p2.y, mid_x, mid_y)

        # Final line to last point
        last_point = points[-1]
        path.lineTo(last_point.x, last_point.y)

    def _create_pen_for_pressure(self, pressure: float) -> QPen:
        """Create a pen with width based on pressure"""
        pen = QPen(QColor(self.stroke.color))

        # Calculate width based on pressure and base thickness
        width = pressure * self.stroke.thickness
        pen.setWidthF(max(0.5, width))  # Minimum width of 0.5

        # Configure pen for smooth rendering
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCosmetic(False)  # Scale with transformations

        return pen

    def _has_varying_pressure(self) -> bool:
        """Check if the stroke has significantly varying pressure values"""
        if len(self.stroke.points) < 2:
            return False

        pressures = [p.pressure for p in self.stroke.points]
        min_pressure = min(pressures)
        max_pressure = max(pressures)

        # Consider pressure varying if there's more than 20% difference
        return (max_pressure - min_pressure) > 0.2

    def add_point(self, point: Point) -> None:
        """Add a point to the stroke and update the graphics"""
        self.stroke.points.append(point)

        # Invalidate caches
        self._stroke_path = None
        self.invalidate_cache()

    def set_points(self, points: list[Point]) -> None:
        """Set all points for the stroke"""
        self.stroke.points = points

        # Invalidate caches
        self._stroke_path = None
        self.invalidate_cache()

    def intersects_point(self, point: QPointF, radius: float = 5.0) -> bool:
        """Check if the stroke intersects with a point within the given radius"""
        return self.stroke.intersects(Point(point.x(), point.y(), 1.0), radius)

    @override
    def type(self) -> int:
        """Return unique type identifier for stroke items"""
        return hash("StrokeGraphicsItem") & 0x7FFFFFFF

    def clone(self) -> "StrokeGraphicsItem":
        """Create a copy of this stroke graphics item"""
        # Create a new stroke with copied data
        new_stroke = Stroke(
            points=self.stroke.points.copy(),
            color=self.stroke.color,
            size=self.stroke.thickness,
            tool=self.stroke.tool,
        )
        return StrokeGraphicsItem(new_stroke)
