"""Stroke beautification using template matching and recognition."""

import math
from dataclasses import dataclass

from diary.models import Point


@dataclass
class StrokeTemplate:
    """A template for a recognized stroke shape."""

    name: str
    points: list[Point]  # Normalized template points


class StrokeBeautifier:
    """
    Recognizes and beautifies strokes using $1 Unistroke Recognizer algorithm.
    Based on: http://depts.washington.edu/acelab/proj/dollar/index.html
    """

    SAMPLE_POINTS: int = 64
    SQUARE_SIZE: float = 250.0

    def __init__(self):
        self.templates: list[StrokeTemplate] = []
        self._load_templates()

    def _load_templates(self):
        """Load geometric shape templates."""
        # Line (rotation handled during matching)
        self.templates.append(
            StrokeTemplate("line", [Point(i / 63, 0.5, 1.0) for i in range(64)])
        )

        # Circle (clockwise)
        circle_points = [
            Point(
                0.5 + 0.45 * math.cos(2 * math.pi * i / 64),
                0.5 + 0.45 * math.sin(2 * math.pi * i / 64),
                1.0,
            )
            for i in range(64)
        ]
        self.templates.append(StrokeTemplate("circle", circle_points))

    def beautify_stroke(
        self, stroke_points: list[Point], threshold: float = 0.70
    ) -> tuple[list[Point], str | None]:
        """
        Attempt to recognize and beautify a stroke.

        Args:
            stroke_points: Original stroke points
            threshold: Recognition confidence threshold (0-1)

        Returns:
            Tuple of (beautified points, recognized shape name or None)
        """
        if len(stroke_points) < 10:
            return stroke_points, None

        # Normalize the input stroke
        normalized = self._normalize_stroke(stroke_points)

        # Find best matching template (try multiple rotations for rotation invariance)
        best_score = 0.0
        best_template: StrokeTemplate | None = None

        for template in self.templates:
            # Try fewer rotation angles to avoid false matches
            # Only try 0° and 90° for most shapes
            angles = (
                [0, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165]
                if "line" in template.name
                else [0, 90]
            )

            for angle in angles:
                rotated = self._rotate_points(normalized, angle)
                score = self._calculate_similarity(rotated, template.points)
                if score > best_score:
                    best_score = score
                    best_template = template

        print(
            f"Best match: {best_template.name if best_template else 'None'}, score: {best_score:.3f}"
        )

        if best_score >= threshold and best_template:
            if best_template.name == "circle":
                min_x = min(p.x for p in stroke_points)
                max_x = max(p.x for p in stroke_points)
                min_y = min(p.y for p in stroke_points)
                max_y = max(p.y for p in stroke_points)
                width = max_x - min_x
                height = max_y - min_y
                min_dim = min(width, height)
                max_dim = max(width, height)
                if min_dim == 0 or max_dim == 0:
                    return stroke_points, None
                aspect_ratio = min_dim / max_dim
                if aspect_ratio < 0.9:
                    return stroke_points, None
            # Shape was recognized, return beautified version
            beautified = self._generate_beautified_stroke(stroke_points, best_template)
            return beautified, best_template.name

        return stroke_points, None

    def _normalize_stroke(self, points: list[Point]) -> list[Point]:
        """Resample, scale, and translate stroke to standard form."""
        # Resample to fixed number of points
        resampled = self._resample(points, self.SAMPLE_POINTS)

        # Find bounding box
        min_x = min(p.x for p in resampled)
        max_x = max(p.x for p in resampled)
        min_y = min(p.y for p in resampled)
        max_y = max(p.y for p in resampled)

        width = max_x - min_x
        height = max_y - min_y

        if width < 1 and height < 1:
            return resampled

        # Scale to unit square
        scale = max(width, height)
        normalized = []
        for p in resampled:
            nx = (p.x - min_x) / scale if scale > 0 else 0.5
            ny = (p.y - min_y) / scale if scale > 0 else 0.5
            normalized.append(Point(nx, ny, p.pressure))

        # Translate to center to make line orientation/position comparable
        cx = sum(p.x for p in normalized) / len(normalized)
        cy = sum(p.y for p in normalized) / len(normalized)
        centered = [
            Point(p.x + (0.5 - cx), p.y + (0.5 - cy), p.pressure) for p in normalized
        ]

        return centered

    def _resample(self, points: list[Point], n: int) -> list[Point]:
        """Resample stroke to n evenly-spaced points."""
        path_length = self._path_length(points)
        if path_length == 0:
            return points

        interval = path_length / (n - 1)

        resampled = [points[0]]
        accumulated = 0.0

        i = 1
        while i < len(points) and len(resampled) < n:
            d = self._distance(points[i - 1], points[i])

            if accumulated + d >= interval:
                # Interpolate new point
                t = (interval - accumulated) / d if d > 0 else 0
                nx = points[i - 1].x + t * (points[i].x - points[i - 1].x)
                ny = points[i - 1].y + t * (points[i].y - points[i - 1].y)
                np_ = points[i - 1].pressure + t * (
                    points[i].pressure - points[i - 1].pressure
                )

                new_point = Point(nx, ny, np_)
                resampled.append(new_point)
                points = [new_point] + points[i:]
                i = 1
                accumulated = 0.0
            else:
                accumulated += d
                i += 1

        # Ensure we have exactly n points
        while len(resampled) < n:
            resampled.append(resampled[-1])

        return resampled[:n]

    def _path_length(self, points: list[Point]) -> float:
        """Calculate total path length."""
        return sum(
            self._distance(points[i], points[i + 1]) for i in range(len(points) - 1)
        )

    def _distance(self, p1: Point, p2: Point) -> float:
        """Euclidean distance between two points."""
        dx = p2.x - p1.x
        dy = p2.y - p1.y
        return math.sqrt(dx * dx + dy * dy)

    def _rotate_points(self, points: list[Point], angle_degrees: float) -> list[Point]:
        """Rotate points around center by given angle."""
        if angle_degrees == 0:
            return points

        # Calculate center
        cx = sum(p.x for p in points) / len(points)
        cy = sum(p.y for p in points) / len(points)

        # Convert to radians
        angle_rad = math.radians(angle_degrees)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)

        # Rotate each point
        rotated = []
        for p in points:
            # Translate to origin
            x = p.x - cx
            y = p.y - cy

            # Rotate
            rx = x * cos_a - y * sin_a
            ry = x * sin_a + y * cos_a

            # Translate back
            rotated.append(Point(rx + cx, ry + cy, p.pressure))

        return rotated

    def _calculate_similarity(
        self, stroke: list[Point], template: list[Point]
    ) -> float:
        """Calculate similarity score between stroke and template (0-1)."""
        if len(stroke) != len(template):
            return 0.0

        total_dist = sum(
            self._distance(stroke[i], template[i]) for i in range(len(stroke))
        )
        avg_dist = total_dist / len(stroke)

        # Convert distance to similarity score (lower distance = higher score)
        # Use exponential decay with adjusted coefficient
        # At avg_dist=0 -> score=1.0
        # At avg_dist=0.3 -> score~0.74
        # At avg_dist=0.5 -> score~0.60
        # At avg_dist=1.0 -> score~0.37
        base_score = math.exp(-avg_dist)

        # Add direction variance check for better discrimination
        # Lines should have consistent direction, circles/complex shapes should vary
        direction_variance = self._calculate_direction_variance(stroke)
        template_variance = self._calculate_direction_variance(template)

        # Penalize if direction variance doesn't match
        variance_diff = abs(direction_variance - template_variance)
        variance_penalty = math.exp(-variance_diff * 2)

        return base_score * (0.7 + 0.3 * variance_penalty)

    def _calculate_direction_variance(self, points: list[Point]) -> float:
        """Calculate variance in direction changes along the stroke."""
        if len(points) < 3:
            return 0.0

        angles = []
        for i in range(1, len(points) - 1):
            dx1 = points[i].x - points[i - 1].x
            dy1 = points[i].y - points[i - 1].y
            dx2 = points[i + 1].x - points[i].x
            dy2 = points[i + 1].y - points[i].y

            # Calculate angle change
            angle1 = math.atan2(dy1, dx1)
            angle2 = math.atan2(dy2, dx2)
            angle_diff = abs(angle2 - angle1)
            # Normalize to [0, pi]
            if angle_diff > math.pi:
                angle_diff = 2 * math.pi - angle_diff
            angles.append(angle_diff)

        # Return average angle change (higher = more curved/complex)
        return sum(angles) / len(angles) if angles else 0.0

    def _generate_beautified_stroke(
        self, original: list[Point], template: StrokeTemplate
    ) -> list[Point]:
        """Generate beautified stroke maintaining original bounds and position."""
        if template.name == "line":
            start = original[0]
            end = original[-1]
            avg_pressure = sum(p.pressure for p in original) / len(original)
            count = len(template.points)
            beautified = []
            for i in range(count):
                t = i / (count - 1) if count > 1 else 0.0
                x = start.x + t * (end.x - start.x)
                y = start.y + t * (end.y - start.y)
                beautified.append(Point(x, y, avg_pressure))
            return beautified

        # Get original bounding box
        min_x = min(p.x for p in original)
        max_x = max(p.x for p in original)
        min_y = min(p.y for p in original)
        max_y = max(p.y for p in original)

        width = max_x - min_x
        height = max_y - min_y
        if template.name == "circle":
            size = min(width, height)
            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2
            min_x = center_x - size / 2
            min_y = center_y - size / 2
            width = size
            height = size

        # Average pressure from original
        avg_pressure = sum(p.pressure for p in original) / len(original)

        # Map template to original bounds
        beautified = []
        for tp in template.points:
            x = min_x + tp.x * width
            y = min_y + tp.y * height
            beautified.append(Point(x, y, avg_pressure))

        return beautified
