"""
Converts Stroke elements to PIL Images for OCR processing.

Groups nearby strokes and renders them to images suitable for OCR.
"""

import hashlib
from dataclasses import dataclass

from PIL import Image, ImageDraw

from diary.config import settings
from diary.models.elements import Stroke


@dataclass
class BoundingBox:
    """Represents a bounding box for a group of strokes."""

    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    def expand(self, padding: float) -> "BoundingBox":
        """Return a new bounding box expanded by padding on all sides."""
        return BoundingBox(
            min_x=self.min_x - padding,
            min_y=self.min_y - padding,
            max_x=self.max_x + padding,
            max_y=self.max_y + padding,
        )

    def intersects(self, other: "BoundingBox", gap: float) -> bool:
        """Check if two bounding boxes are within gap distance of each other."""
        return not (
            self.max_x + gap < other.min_x
            or other.max_x + gap < self.min_x
            or self.max_y + gap < other.min_y
            or other.max_y + gap < self.min_y
        )

    def merge(self, other: "BoundingBox") -> "BoundingBox":
        """Merge two bounding boxes into one that contains both."""
        return BoundingBox(
            min_x=min(self.min_x, other.min_x),
            min_y=min(self.min_y, other.min_y),
            max_x=max(self.max_x, other.max_x),
            max_y=max(self.max_y, other.max_y),
        )


@dataclass
class StrokeGroup:
    """A group of spatially related strokes."""

    strokes: list[Stroke]
    bounding_box: BoundingBox

    @property
    def stroke_ids(self) -> list[str]:
        """Get all stroke element IDs in this group."""
        return [s.element_id for s in self.strokes]


class StrokeRasterizer:
    """Converts stroke groups to images for OCR processing."""

    # Rendering constants
    SCALE_FACTOR: float = (
        settings.OCR_STROKE_SCALE_FACTOR
    )  # Scale up for better OCR quality
    PADDING: float = settings.OCR_STROKE_PADDING  # Padding around strokes in pixels
    MIN_IMAGE_SIZE: int = settings.OCR_MIN_IMAGE_SIZE  # Minimum dimension for OCR
    BACKGROUND_COLOR: str = "#FFFFFF"
    STROKE_COLOR: str = "#000000"

    @staticmethod
    def get_stroke_bounding_box(stroke: Stroke) -> BoundingBox | None:
        """Calculate the bounding box for a single stroke."""
        if not stroke.points:
            return None

        min_x = min(p.x for p in stroke.points)
        min_y = min(p.y for p in stroke.points)
        max_x = max(p.x for p in stroke.points)
        max_y = max(p.y for p in stroke.points)

        return BoundingBox(min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y)

    @staticmethod
    def group_strokes_by_proximity(
        strokes: list[Stroke], gap: float | None = None
    ) -> list[StrokeGroup]:
        """
        Group strokes that are within gap distance of each other.

        Uses union-find algorithm to efficiently cluster nearby strokes.

        Args:
            strokes: List of strokes to group
            gap: Maximum gap between strokes to be in same group.
                 Defaults to OCR_STROKE_GROUPING_GAP from settings.

        Returns:
            List of StrokeGroup objects, each containing related strokes.
        """
        if gap is None:
            gap = settings.OCR_STROKE_GROUPING_GAP

        # Calculate bounding boxes for all strokes
        stroke_boxes: list[tuple[Stroke, BoundingBox]] = []
        for stroke in strokes:
            bbox = StrokeRasterizer.get_stroke_bounding_box(stroke)
            if bbox is not None:
                stroke_boxes.append((stroke, bbox))

        if not stroke_boxes:
            return []

        # Union-find data structure
        n = len(stroke_boxes)
        parent = list(range(n))

        def find(x: int) -> int:
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x: int, y: int) -> None:
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        # Merge strokes that are within gap distance
        for i in range(n):
            for j in range(i + 1, n):
                if stroke_boxes[i][1].intersects(stroke_boxes[j][1], gap):
                    union(i, j)

        # Build groups from union-find structure
        groups_dict: dict[int, list[int]] = {}
        for i in range(n):
            root = find(i)
            if root not in groups_dict:
                groups_dict[root] = []
            groups_dict[root].append(i)

        # Create StrokeGroup objects
        groups: list[StrokeGroup] = []
        for indices in groups_dict.values():
            group_strokes = [stroke_boxes[i][0] for i in indices]
            group_bbox = stroke_boxes[indices[0]][1]
            for i in indices[1:]:
                group_bbox = group_bbox.merge(stroke_boxes[i][1])
            groups.append(StrokeGroup(strokes=group_strokes, bounding_box=group_bbox))

        return groups

    @staticmethod
    def render_stroke_group(group: StrokeGroup) -> Image.Image:
        """
        Render a group of strokes to a PIL Image.

        The image is rendered at 2x scale with white background
        and black strokes for optimal OCR processing.

        Args:
            group: StrokeGroup to render

        Returns:
            PIL Image containing the rendered strokes
        """
        bbox = group.bounding_box.expand(StrokeRasterizer.PADDING)
        scale = StrokeRasterizer.SCALE_FACTOR

        # Calculate image dimensions
        width = max(int(bbox.width * scale), StrokeRasterizer.MIN_IMAGE_SIZE)
        height = max(int(bbox.height * scale), StrokeRasterizer.MIN_IMAGE_SIZE)

        # Create image with white background
        image = Image.new("L", (width, height), color=255)  # Grayscale, white
        draw = ImageDraw.Draw(image)

        # Draw each stroke
        for stroke in group.strokes:
            if len(stroke.points) < 2:
                continue

            # Convert points to scaled coordinates
            points = [
                (
                    (p.x - bbox.min_x) * scale,
                    (p.y - bbox.min_y) * scale,
                )
                for p in stroke.points
            ]

            # Draw stroke as connected lines
            # Use stroke thickness scaled appropriately
            line_width = max(1, int(stroke.thickness * scale * 0.8))
            draw.line(points, fill=0, width=line_width)  # Black on grayscale

        return image

    @staticmethod
    def rasterize_strokes(
        strokes: list[Stroke],
    ) -> list[tuple[Image.Image, StrokeGroup]]:
        """
        Convert a list of strokes to images for OCR.

        Groups nearby strokes and renders each group to a separate image.

        Args:
            strokes: List of Stroke elements to rasterize

        Returns:
            List of (image, stroke_group) tuples for OCR processing
        """
        groups = StrokeRasterizer.group_strokes_by_proximity(strokes)

        results: list[tuple[Image.Image, StrokeGroup]] = []
        for group in groups:
            image = StrokeRasterizer.render_stroke_group(group)
            results.append((image, group))

        return results

    @staticmethod
    def compute_group_id(group: StrokeGroup) -> str:
        """Compute a stable ID for a stroke group based on stroke IDs."""
        stroke_ids = sorted(group.stroke_ids)
        raw = "|".join(stroke_ids)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def compute_group_hash(group: StrokeGroup) -> str:
        """Compute a hash for a stroke group based on stroke content."""
        parts: list[str] = []
        strokes = sorted(group.strokes, key=lambda s: s.element_id)
        for stroke in strokes:
            parts.append(stroke.element_id)
            parts.append(stroke.color)
            parts.append(f"{stroke.thickness:.3f}")
            parts.append(stroke.tool)
            for point in stroke.points:
                parts.append(f"{point.x:.4f},{point.y:.4f},{point.pressure:.4f}")
        raw = "|".join(parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
