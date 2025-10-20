"""Tests for the PageElement system and adapters"""

import unittest
from unittest.mock import Mock
from PyQt6.QtGui import QPainter

from diary.models.page import Page
from diary.models.stroke import Stroke
from diary.models.image import Image
from diary.models.voice_memo import VoiceMemo
from diary.models.point import Point
from diary.ui.adapters import AdapterRegistry
from diary.ui.adapters.stroke_adapter import StrokeAdapter
from diary.ui.adapters.image_adapter import ImageAdapter
from diary.ui.adapters.voice_memo_adapter import VoiceMemoAdapter


class TestPageElements(unittest.TestCase):
    """Test the PageElement system"""

    def setUp(self):
        """Set up test data"""
        self.page = Page()

        # Create test elements
        self.stroke = Stroke(
            points=[Point(10, 10, 1.0), Point(20, 20, 0.8)],
            color="red",
            size=2.0,
            tool="pen",
        )

        self.image = Image(
            position=Point(50, 50, 1.0),
            width=100,
            height=80,
            image_path="/test/image.png",
        )

        self.voice_memo = VoiceMemo(
            position=Point(150, 150, 1.0), duration=30.5, transcript="Hello world"
        )

    def test_page_element_types(self):
        """Test that elements have correct types and unique IDs"""
        self.assertEqual(self.stroke.element_type, "stroke")
        self.assertEqual(self.image.element_type, "image")
        self.assertEqual(self.voice_memo.element_type, "voice_memo")

        # Test that each element has a unique ID
        self.assertIsNotNone(self.stroke.element_id)
        self.assertIsNotNone(self.image.element_id)
        self.assertIsNotNone(self.voice_memo.element_id)

        # Test that IDs are different
        self.assertNotEqual(self.stroke.element_id, self.image.element_id)
        self.assertNotEqual(self.stroke.element_id, self.voice_memo.element_id)
        self.assertNotEqual(self.image.element_id, self.voice_memo.element_id)

    def test_page_add_elements(self):
        """Test adding elements to a page"""
        self.page.add_element(self.stroke)
        self.page.add_element(self.image)
        self.page.add_element(self.voice_memo)

        self.assertEqual(len(self.page.elements), 3)
        self.assertIn(self.stroke, self.page.elements)
        self.assertIn(self.image, self.page.elements)
        self.assertIn(self.voice_memo, self.page.elements)

    def test_page_remove_elements(self):
        """Test removing elements from a page"""
        self.page.add_element(self.stroke)
        self.page.add_element(self.image)

        self.page.remove_element(self.stroke)

        self.assertEqual(len(self.page.elements), 1)
        self.assertNotIn(self.stroke, self.page.elements)
        self.assertIn(self.image, self.page.elements)

    def test_page_clear_elements(self):
        """Test clearing all elements from a page"""
        self.page.add_element(self.stroke)
        self.page.add_element(self.image)

        self.page.clear_elements()

        self.assertEqual(len(self.page.elements), 0)

    def test_backward_compatibility_strokes_property(self):
        """Test that the strokes property still works for backward compatibility"""
        self.page.add_element(self.stroke)
        self.page.add_element(self.image)  # Non-stroke element

        strokes = self.page.strokes
        self.assertEqual(len(strokes), 1)
        self.assertIn(self.stroke, strokes)
        self.assertNotIn(self.image, strokes)

    def test_element_serialization(self):
        """Test element serialization to dict"""
        stroke_dict = self.stroke.to_dict()
        image_dict = self.image.to_dict()
        voice_memo_dict = self.voice_memo.to_dict()

        # Check stroke serialization
        self.assertEqual(stroke_dict["ty"], "stroke")
        self.assertEqual(len(stroke_dict["p"]), 2)
        self.assertEqual(stroke_dict["c"], "red")
        self.assertIn("id", stroke_dict)
        self.assertEqual(stroke_dict["id"], self.stroke.element_id)

        # Check image serialization
        self.assertEqual(image_dict["ty"], "image")
        self.assertEqual(image_dict["w"], 100)
        self.assertEqual(image_dict["h"], 80)
        self.assertIn("id", image_dict)
        self.assertEqual(image_dict["id"], self.image.element_id)

        # Check voice memo serialization
        self.assertEqual(voice_memo_dict["ty"], "voice_memo")
        self.assertEqual(voice_memo_dict["d"], 30.5)
        self.assertEqual(voice_memo_dict["t"], "Hello world")
        self.assertIn("id", voice_memo_dict)
        self.assertEqual(voice_memo_dict["id"], self.voice_memo.element_id)

    def test_element_deserialization(self):
        """Test element deserialization from dict"""
        # Test stroke deserialization
        stroke_dict = self.stroke.to_dict()
        restored_stroke = Stroke.from_dict(stroke_dict)

        self.assertEqual(restored_stroke, self.stroke)
        self.assertEqual(len(restored_stroke.points), 2)
        self.assertEqual(restored_stroke.color, "red")
        self.assertEqual(restored_stroke.element_id, self.stroke.element_id)

        # Test image deserialization
        image_dict = self.image.to_dict()
        restored_image = Image.from_dict(image_dict)

        self.assertEqual(restored_image, self.image)
        self.assertEqual(restored_image.width, 100)
        self.assertEqual(restored_image.height, 80)
        self.assertEqual(restored_image.element_id, self.image.element_id)

        # Test voice memo deserialization
        voice_memo_dict = self.voice_memo.to_dict()
        restored_voice_memo = VoiceMemo.from_dict(voice_memo_dict)

        self.assertEqual(restored_voice_memo, self.voice_memo)
        self.assertEqual(restored_voice_memo.duration, 30.5)
        self.assertEqual(restored_voice_memo.transcript, "Hello world")
        self.assertEqual(restored_voice_memo.element_id, self.voice_memo.element_id)

    def test_element_intersection(self):
        """Test element intersection detection"""
        # Test stroke intersection
        self.assertTrue(self.stroke.intersects(Point(15, 15, 1.0), 10))
        self.assertFalse(self.stroke.intersects(Point(100, 100, 1.0), 5))

        # Test image intersection
        self.assertTrue(self.image.intersects(Point(75, 75, 1.0), 10))
        self.assertFalse(self.image.intersects(Point(200, 200, 1.0), 5))

        # Test voice memo intersection
        self.assertTrue(self.voice_memo.intersects(Point(170, 170, 1.0), 10))
        self.assertFalse(self.voice_memo.intersects(Point(50, 50, 1.0), 5))

    def test_element_uuid_equality(self):
        """Test that elements with same UUID are considered equal"""
        # Create two stroke elements with the same UUID
        uuid_id = "test-uuid-123"
        stroke1 = Stroke(
            points=[Point(10, 10, 1.0)], color="blue", size=1.0, element_id=uuid_id
        )
        stroke2 = Stroke(
            points=[Point(20, 20, 1.0)], color="red", size=2.0, element_id=uuid_id
        )

        # They should be equal because they have the same UUID
        self.assertEqual(stroke1, stroke2)

        # Test with different UUIDs
        stroke3 = Stroke(
            points=[Point(10, 10, 1.0)],
            color="blue",
            size=1.0,
            element_id="different-uuid",
        )
        self.assertNotEqual(stroke1, stroke3)


class TestAdapterSystem(unittest.TestCase):
    """Test the adapter system"""

    def setUp(self):
        """Set up test adapters and registry"""
        self.registry = AdapterRegistry()
        self.stroke_adapter = StrokeAdapter()
        self.image_adapter = ImageAdapter()
        self.voice_memo_adapter = VoiceMemoAdapter()

        self.registry.register(self.stroke_adapter)
        self.registry.register(self.image_adapter)
        self.registry.register(self.voice_memo_adapter)

        # Create test elements
        self.stroke = Stroke(
            points=[Point(10, 10, 1.0), Point(20, 20, 0.8)], color="blue", size=1.5
        )
        self.image = Image(Point(50, 50, 1.0), 100, 80)
        self.voice_memo = VoiceMemo(Point(150, 150, 1.0), 45.0)

    def test_adapter_can_handle(self):
        """Test that adapters correctly identify their element types"""
        self.assertTrue(self.stroke_adapter.can_handle(self.stroke))
        self.assertFalse(self.stroke_adapter.can_handle(self.image))
        self.assertFalse(self.stroke_adapter.can_handle(self.voice_memo))

        self.assertTrue(self.image_adapter.can_handle(self.image))
        self.assertFalse(self.image_adapter.can_handle(self.stroke))
        self.assertFalse(self.image_adapter.can_handle(self.voice_memo))

        self.assertTrue(self.voice_memo_adapter.can_handle(self.voice_memo))
        self.assertFalse(self.voice_memo_adapter.can_handle(self.stroke))
        self.assertFalse(self.voice_memo_adapter.can_handle(self.image))

    def test_registry_get_adapter(self):
        """Test that registry returns correct adapters"""
        stroke_adapter = self.registry.get_adapter(self.stroke)
        image_adapter = self.registry.get_adapter(self.image)
        voice_memo_adapter = self.registry.get_adapter(self.voice_memo)

        self.assertIsInstance(stroke_adapter, StrokeAdapter)
        self.assertIsInstance(image_adapter, ImageAdapter)
        self.assertIsInstance(voice_memo_adapter, VoiceMemoAdapter)

    def test_registry_render_element(self):
        """Test that registry can render elements"""
        # Create a mock painter
        mock_painter = Mock(spec=QPainter)

        # Test rendering different elements
        result_stroke = self.registry.render_element(self.stroke, mock_painter)
        result_image = self.registry.render_element(self.image, mock_painter)
        result_voice_memo = self.registry.render_element(self.voice_memo, mock_painter)

        # All should return True (successfully found adapters)
        self.assertTrue(result_stroke)
        self.assertTrue(result_image)
        self.assertTrue(result_voice_memo)

    def test_registry_unknown_element_type(self):
        """Test that registry handles unknown element types gracefully"""
        # Create a mock element with unknown type
        mock_element = Mock()
        mock_element.element_type = "unknown"

        mock_painter = Mock(spec=QPainter)

        result = self.registry.render_element(mock_element, mock_painter)

        # Should return False (no adapter found)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
