"""Tests for stroke rasterization"""

from diary.models.elements.stroke import Stroke
from diary.models.point import Point
from diary.search.stroke_rasterizer import BoundingBox, StrokeGroup, StrokeRasterizer


class TestBoundingBox:
    """Tests for the BoundingBox dataclass"""

    def test_width_height(self):
        """Test width and height calculations"""
        bbox = BoundingBox(min_x=10, min_y=20, max_x=50, max_y=80)
        assert bbox.width == 40
        assert bbox.height == 60

    def test_expand(self):
        """Test bounding box expansion"""
        bbox = BoundingBox(min_x=10, min_y=20, max_x=50, max_y=80)
        expanded = bbox.expand(5)

        assert expanded.min_x == 5
        assert expanded.min_y == 15
        assert expanded.max_x == 55
        assert expanded.max_y == 85

    def test_intersects_overlapping(self):
        """Test intersection detection for overlapping boxes"""
        bbox1 = BoundingBox(min_x=0, min_y=0, max_x=10, max_y=10)
        bbox2 = BoundingBox(min_x=5, min_y=5, max_x=15, max_y=15)

        assert bbox1.intersects(bbox2, gap=0)
        assert bbox2.intersects(bbox1, gap=0)

    def test_intersects_with_gap(self):
        """Test intersection detection with gap distance"""
        bbox1 = BoundingBox(min_x=0, min_y=0, max_x=10, max_y=10)
        bbox2 = BoundingBox(min_x=15, min_y=0, max_x=25, max_y=10)

        # Gap of 5 - boxes are 5 apart
        assert bbox1.intersects(bbox2, gap=5)
        # Gap of 4 - boxes too far apart
        assert not bbox1.intersects(bbox2, gap=4)

    def test_intersects_non_overlapping(self):
        """Test intersection detection for non-overlapping boxes"""
        bbox1 = BoundingBox(min_x=0, min_y=0, max_x=10, max_y=10)
        bbox2 = BoundingBox(min_x=20, min_y=20, max_x=30, max_y=30)

        assert not bbox1.intersects(bbox2, gap=0)

    def test_merge(self):
        """Test merging two bounding boxes"""
        bbox1 = BoundingBox(min_x=0, min_y=0, max_x=10, max_y=10)
        bbox2 = BoundingBox(min_x=5, min_y=5, max_x=20, max_y=20)

        merged = bbox1.merge(bbox2)

        assert merged.min_x == 0
        assert merged.min_y == 0
        assert merged.max_x == 20
        assert merged.max_y == 20


class TestStrokeRasterizer:
    """Tests for the StrokeRasterizer class"""

    def test_get_stroke_bounding_box(self):
        """Test calculating bounding box for a stroke"""
        stroke = Stroke(
            points=[Point(10, 20, 1), Point(30, 40, 1), Point(20, 50, 1)],
            color="black",
            size=2.0,
        )

        bbox = StrokeRasterizer.get_stroke_bounding_box(stroke)

        assert bbox is not None
        assert bbox.min_x == 10
        assert bbox.min_y == 20
        assert bbox.max_x == 30
        assert bbox.max_y == 50

    def test_get_stroke_bounding_box_empty(self):
        """Test bounding box for stroke with no points"""
        stroke = Stroke(points=[], color="black", size=2.0)
        bbox = StrokeRasterizer.get_stroke_bounding_box(stroke)
        assert bbox is None

    def test_group_strokes_by_proximity_single(self):
        """Test grouping a single stroke"""
        stroke = Stroke(
            points=[Point(10, 10, 1), Point(20, 20, 1)],
            color="black",
            size=2.0,
        )

        groups = StrokeRasterizer.group_strokes_by_proximity([stroke], gap=50)

        assert len(groups) == 1
        assert len(groups[0].strokes) == 1
        assert groups[0].strokes[0] == stroke

    def test_group_strokes_by_proximity_close(self):
        """Test grouping nearby strokes together"""
        stroke1 = Stroke(
            points=[Point(0, 0, 1), Point(10, 10, 1)],
            color="black",
            size=2.0,
        )
        stroke2 = Stroke(
            points=[Point(20, 0, 1), Point(30, 10, 1)],
            color="black",
            size=2.0,
        )

        # Gap of 50 should group them together (10 pixel gap)
        groups = StrokeRasterizer.group_strokes_by_proximity([stroke1, stroke2], gap=50)

        assert len(groups) == 1
        assert len(groups[0].strokes) == 2

    def test_group_strokes_by_proximity_far(self):
        """Test that far-apart strokes are in separate groups"""
        stroke1 = Stroke(
            points=[Point(0, 0, 1), Point(10, 10, 1)],
            color="black",
            size=2.0,
        )
        stroke2 = Stroke(
            points=[Point(200, 0, 1), Point(210, 10, 1)],
            color="black",
            size=2.0,
        )

        # Gap of 50 should keep them separate (190 pixel gap)
        groups = StrokeRasterizer.group_strokes_by_proximity([stroke1, stroke2], gap=50)

        assert len(groups) == 2
        assert len(groups[0].strokes) == 1
        assert len(groups[1].strokes) == 1

    def test_group_strokes_empty_list(self):
        """Test grouping empty list of strokes"""
        groups = StrokeRasterizer.group_strokes_by_proximity([], gap=50)
        assert len(groups) == 0

    def test_render_stroke_group(self):
        """Test rendering a stroke group to image"""
        stroke = Stroke(
            points=[Point(10, 10, 1), Point(50, 50, 1), Point(90, 10, 1)],
            color="black",
            size=2.0,
        )
        bbox = BoundingBox(min_x=10, min_y=10, max_x=90, max_y=50)
        group = StrokeGroup(strokes=[stroke], bounding_box=bbox)

        image = StrokeRasterizer.render_stroke_group(group)

        # Image should be created with appropriate dimensions
        assert image is not None
        assert image.mode == "L"  # Grayscale
        assert image.width >= 32  # Minimum size
        assert image.height >= 32

    def test_rasterize_strokes(self):
        """Test full rasterization pipeline"""
        strokes = [
            Stroke(
                points=[Point(0, 0, 1), Point(20, 20, 1)],
                color="black",
                size=2.0,
            ),
            Stroke(
                points=[Point(10, 0, 1), Point(30, 20, 1)],
                color="black",
                size=2.0,
            ),
        ]

        results = StrokeRasterizer.rasterize_strokes(strokes)

        assert len(results) >= 1
        for image, group in results:
            assert image is not None
            assert len(group.strokes) > 0

    def test_stroke_group_ids(self):
        """Test StrokeGroup.stroke_ids property"""
        stroke1 = Stroke(points=[Point(0, 0, 1)], color="black", size=1)
        stroke2 = Stroke(points=[Point(10, 10, 1)], color="black", size=1)
        bbox = BoundingBox(min_x=0, min_y=0, max_x=10, max_y=10)

        group = StrokeGroup(strokes=[stroke1, stroke2], bounding_box=bbox)

        assert len(group.stroke_ids) == 2
        assert stroke1.element_id in group.stroke_ids
        assert stroke2.element_id in group.stroke_ids
