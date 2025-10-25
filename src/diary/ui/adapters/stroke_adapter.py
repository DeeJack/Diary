"""Adapter for rendering Stroke elements with QPainter"""

from typing import override

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen

from diary.config import settings
from diary.models import PageElement, Point, Stroke
from diary.ui.adapters import ElementAdapter


class StrokeAdapter(ElementAdapter):
    """Adapter for rendering Stroke elements with crisp, smooth curves"""

    def __init__(self, base_thickness: float = 3.0):
        self.base_thickness: float = base_thickness

    @override
    def can_handle(self, element: PageElement) -> bool:
        """Check if this adapter can handle the given element type"""
        return isinstance(element, Stroke)

    @override
    def render(self, element: PageElement, painter: QPainter) -> None:
        """Render the stroke using the provided QPainter with crisp, smooth curves"""
        if not isinstance(element, Stroke):
            return

        stroke = element
        if len(stroke.points) < 1:
            return

        # Save painter state
        painter.save()

        # Configure painter for crisp rendering
        self._configure_painter_for_crisp_rendering(painter)

        if len(stroke.points) == 1:
            self._render_single_point(stroke, painter)
        else:
            self._render_smooth_path(stroke, painter)

        # Restore painter state
        painter.restore()

    def _configure_painter_for_crisp_rendering(self, painter: QPainter) -> None:
        """Configure painter settings for optimal stroke rendering"""
        # Enable high-quality antialiasing
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

    def _render_single_point(self, stroke: Stroke, painter: QPainter) -> None:
        """Render a single point as a dot"""
        first_point = stroke.points[0]
        width = first_point.pressure

        pen = self._create_optimized_pen(stroke.color, width)
        painter.setPen(pen)
        painter.drawPoint(QPointF(first_point.x, first_point.y))

    def _render_smooth_path(self, stroke: Stroke, painter: QPainter) -> None:
        """Render the entire stroke as a single smooth path"""
        if len(stroke.points) < 2:
            return

        # Create a single path for the entire stroke
        path = QPainterPath()

        # Use variable width if pressure sensitivity is enabled
        if settings.USE_PRESSURE and self._has_varying_pressure(stroke):
            self._render_variable_width_stroke(stroke, painter)
        else:
            self._render_uniform_width_stroke(stroke, painter, path)

    def _render_uniform_width_stroke(
        self, stroke: Stroke, painter: QPainter, path: QPainterPath
    ) -> None:
        """Render stroke with uniform width using a single smooth path"""
        points = stroke.points

        # Calculate average pressure for uniform width
        width = sum(p.pressure for p in points) / len(points)

        # Create optimized pen
        pen = self._create_optimized_pen(stroke.color, width)
        painter.setPen(pen)

        # Build smooth path
        path.moveTo(points[0].x, points[0].y)

        if len(points) == 2:
            # Simple line for two points
            path.lineTo(points[1].x, points[1].y)
        else:
            # Create smooth curves using quadratic Bezier curves
            self._build_smooth_curve_path(points, path)

        # Draw the entire path at once
        painter.drawPath(path)

    def _render_variable_width_stroke(self, stroke: Stroke, painter: QPainter) -> None:
        """Render stroke with variable width based on pressure"""
        points = stroke.points

        # For variable width, we need to draw segments but with better blending
        for i in range(len(points) - 1):
            p1 = points[i]
            p2 = points[i + 1]

            # Calculate width for this segment
            width = (p1.pressure + p2.pressure) / 2

            # Create path for this segment
            segment_path = QPainterPath()
            segment_path.moveTo(p1.x, p1.y)

            if i < len(points) - 2:
                # Use quadratic curve to next point
                p3 = points[i + 2]
                mid_x = (p2.x + p3.x) / 2
                mid_y = (p2.y + p3.y) / 2
                segment_path.quadTo(p2.x, p2.y, mid_x, mid_y)
            else:
                # Last segment - draw line to end
                segment_path.lineTo(p2.x, p2.y)

            # Create pen for this segment
            pen = self._create_optimized_pen(stroke.color, width)
            painter.setPen(pen)

            # Draw segment
            painter.drawPath(segment_path)

    def _build_smooth_curve_path(self, points: list[Point], path: QPainterPath) -> None:
        """Build a smooth curve path through all points using Bezier curves"""
        if len(points) < 3:
            if len(points) == 2:
                path.lineTo(points[1].x, points[1].y)
            return

        # Start with line to first control point
        path.lineTo(points[1].x, points[1].y)

        # Create smooth curves through the middle points
        for i in range(1, len(points) - 2):
            # Calculate control points for smooth curves
            p2 = points[i + 1]
            p3 = points[i + 2]

            # Use the current point as control and midpoint to next as end
            mid_x = (p2.x + p3.x) / 2
            mid_y = (p2.y + p3.y) / 2

            path.quadTo(p2.x, p2.y, mid_x, mid_y)

        # Final line to last point
        last_point = points[-1]
        path.lineTo(last_point.x, last_point.y)

    def _create_optimized_pen(self, color: str, width: float) -> QPen:
        """Create an optimized pen for crisp stroke rendering"""
        pen = QPen(QColor(color))

        # Set width with subpixel precision
        pen.setWidthF(width)

        # Configure pen for smooth, crisp rendering
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

        # Don't use cosmetic pen to maintain proper scaling
        pen.setCosmetic(False)

        return pen

    def _has_varying_pressure(self, stroke: Stroke) -> bool:
        """Check if the stroke has significantly varying pressure values"""
        if len(stroke.points) < 2:
            return False

        pressures = [p.pressure for p in stroke.points]
        min_pressure = min(pressures)
        max_pressure = max(pressures)

        # Consider pressure varying if there's more than 20% difference
        return (max_pressure - min_pressure) > 0.2

    @staticmethod
    def stroke_to_bounding_rect(stroke: Stroke):
        """
        Calculates the smallest rectangle that encloses the entire stroke,
        including its thickness.
        """
        if not stroke.points:
            # Return an empty/invalid rectangle if there are no points
            return QRectF()

        # Initialize min/max with the coordinates of the first point
        min_x = stroke.points[0].x
        max_x = stroke.points[0].x
        min_y = stroke.points[0].y
        max_y = stroke.points[0].y

        # Iterate through the rest of the points to find the extremities
        for point in stroke.points[1:]:
            min_x = min(min_x, point.x)
            max_x = max(max_x, point.x)
            min_y = min(min_y, point.y)
            max_y = max(max_y, point.y)

        margin = stroke.thickness / 2.0

        return QRectF(
            min_x - margin,
            min_y - margin,
            (max_x - min_x) + stroke.thickness,
            (max_y - min_y) + stroke.thickness,
        )
