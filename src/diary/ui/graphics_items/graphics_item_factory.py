"""Factory for creating graphics items from page elements"""

from PyQt6.QtWidgets import QGraphicsItem

from diary.models.elements.image import Image
from diary.models.elements.stroke import Stroke
from diary.models.elements.text import Text
from diary.models.page_element import PageElement

from .image_graphics_item import ImageGraphicsItem
from .stroke_graphics_item import StrokeGraphicsItem
from .text_graphics_item import TextGraphicsItem


class GraphicsItemFactory:
    """Factory for creating appropriate graphics items from page elements"""

    @staticmethod
    def create_graphics_item(
        element: PageElement, parent: QGraphicsItem | None = None
    ) -> QGraphicsItem | None:
        """Create the appropriate graphics item for the given page element"""
        if isinstance(element, Stroke):
            return StrokeGraphicsItem(element, parent)
        if isinstance(element, Text):
            return TextGraphicsItem(element, parent)
        if isinstance(element, Image):
            return ImageGraphicsItem(element, parent)
        return None

    @staticmethod
    def create_stroke_item(
        stroke: Stroke, parent: QGraphicsItem | None = None
    ) -> StrokeGraphicsItem:
        """Create a stroke graphics item"""
        return StrokeGraphicsItem(stroke, parent)

    @staticmethod
    def create_text_item(
        text: Text, parent: QGraphicsItem | None = None
    ) -> TextGraphicsItem:
        """Create a text graphics item"""
        return TextGraphicsItem(text, parent)

    @staticmethod
    def create_image_item(
        image: Image, parent: QGraphicsItem | None = None
    ) -> ImageGraphicsItem:
        """Create an image graphics item"""
        return ImageGraphicsItem(image, parent)

    @staticmethod
    def get_supported_element_types() -> list[type]:
        """Get the list of supported page element types"""
        return [Stroke, Text, Image]

    @staticmethod
    def is_supported_element(element: PageElement) -> bool:
        """Check if the element type is supported by the factory"""
        return isinstance(element, (Stroke, Text, Image))

    @staticmethod
    def clone_graphics_item(
        item: StrokeGraphicsItem | TextGraphicsItem | ImageGraphicsItem,
    ) -> QGraphicsItem | None:
        """Clone an existing graphics item"""
        if isinstance(item, StrokeGraphicsItem):
            return item.clone()
        if isinstance(item, TextGraphicsItem):
            return item.clone()
        return item.clone()
