"""Graphics scene manager for diary page elements using QGraphicsItem architecture"""

import logging
from typing import override

from PyQt6.QtCore import QLineF, QObject, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsScene

from diary.config import settings
from diary.models.elements.image import Image
from diary.models.elements.stroke import Stroke
from diary.models.elements.text import Text
from diary.models.page import Page
from diary.models.page_element import PageElement
from diary.models.point import Point

from .graphics_item_factory import GraphicsItemFactory
from .image_graphics_item import ImageGraphicsItem
from .stroke_graphics_item import StrokeGraphicsItem
from .text_graphics_item import TextGraphicsItem


class PageGraphicsScene(QGraphicsScene):
    """Graphics scene for managing diary page elements as QGraphicsItems"""

    # Signals
    element_added: pyqtSignal = pyqtSignal(PageElement)
    element_removed: pyqtSignal = pyqtSignal(str)  # element_id
    element_modified: pyqtSignal = pyqtSignal(PageElement)
    page_modified: pyqtSignal = pyqtSignal()

    def __init__(self, page: Page, parent: QObject | None = None):
        super().__init__(parent)

        self._page: Page = page
        self._element_items: dict[str, QGraphicsItem] = {}
        self._item_elements: dict[QGraphicsItem, PageElement] = {}
        self._logger: logging.Logger = logging.getLogger("PageGraphicsScene")

        # Configure scene properties
        self.setBackgroundBrush(QBrush(QColor(224, 224, 224)))  # Light gray background
        self.setSceneRect(0, 0, settings.PAGE_WIDTH, settings.PAGE_HEIGHT)
        self._load_page_elements()

    @property
    def page(self) -> Page:
        """Get the current page"""
        return self._page

    @page.setter
    def page(self, value: Page) -> None:
        """Set the page and reload all elements"""
        self.clear_all_elements()
        self._page = value
        self._load_page_elements()

    def _load_page_elements(self) -> None:
        """Load all elements from the current page into the scene"""
        if not self._page:
            return

        self._logger.debug("Loading %s elements into scene", len(self._page.elements))

        for element in self._page.elements:
            _ = self.add_element(element)

    def add_element(self, element: PageElement) -> QGraphicsItem | None:
        """Add a page element to the scene as a graphics item"""
        if element.element_id in self._element_items:
            self._logger.warning(
                "Element %s already exists in scene", element.element_id
            )
            return self._element_items[element.element_id]

        # Create graphics item using factory
        graphics_item = GraphicsItemFactory.create_graphics_item(element)
        if not graphics_item:
            self._logger.error(
                "Could not create graphics item for element %s", element.element_id
            )
            return None

        self.addItem(graphics_item)

        # Track the mapping
        self._element_items[element.element_id or ""] = graphics_item
        self._item_elements[graphics_item] = element

        if element not in self._page.elements:
            self._page.elements.append(element)

        self._logger.debug("Added element %s to scene", element.element_id)
        self.element_added.emit(element)
        self.page_modified.emit()

        return graphics_item

    def remove_element(self, element_id: str) -> bool:
        """Remove an element from the scene and page"""
        if element_id not in self._element_items:
            self._logger.warning("Element %s not found in scene", element_id)
            return False

        graphics_item = self._element_items[element_id]
        element = self._item_elements[graphics_item]

        # Remove from scene
        self.removeItem(graphics_item)

        # Remove from tracking
        del self._element_items[element_id]
        del self._item_elements[graphics_item]

        # Remove from page
        if self._page and element in self._page.elements:
            self._page.elements.remove(element)

        self._logger.debug("Removed element %s from scene", element_id)
        self.element_removed.emit(element_id)
        self.page_modified.emit()

        return True

    def remove_element_by_item(self, graphics_item: QGraphicsItem) -> bool:
        """Remove an element by its graphics item"""
        if graphics_item not in self._item_elements:
            return False

        element = self._item_elements[graphics_item]
        return self.remove_element(element.element_id)

    def get_element_by_id(self, element_id: str) -> PageElement | None:
        """Get a page element by its ID"""
        graphics_item = self._element_items.get(element_id)
        if graphics_item:
            return self._item_elements.get(graphics_item)
        return None

    def get_graphics_item_by_id(self, element_id: str) -> QGraphicsItem | None:
        """Get a graphics item by element ID"""
        return self._element_items.get(element_id)

    def get_element_by_item(self, graphics_item: QGraphicsItem) -> PageElement | None:
        """Get a page element by its graphics item"""
        return self._item_elements.get(graphics_item)

    def update_element(self, element: PageElement) -> None:
        """Update an existing element in the scene"""
        graphics_item = self._element_items.get(element.element_id)
        if not graphics_item:
            self._logger.warning("Element %s not found for update", element.element_id)
            return

        # Update the graphics item's element data
        if isinstance(
            graphics_item, (StrokeGraphicsItem, TextGraphicsItem, ImageGraphicsItem)
        ):
            graphics_item.element = element

        self.element_modified.emit(element)
        self.page_modified.emit()

    def clear_all_elements(self) -> None:
        """Clear all elements from the scene"""
        self.clear()
        self._element_items.clear()
        self._item_elements.clear()

        if self._page:
            self._page.elements.clear()

        self.page_modified.emit()

    def get_elements_at_point(self, point: QPointF) -> list[PageElement]:
        """Get all elements that intersect with the given point"""
        elements: list[PageElement] = []

        for graphics_item in self.items(point):
            element = self._item_elements.get(graphics_item)
            if element:
                elements.append(element)

        return elements

    def get_elements_in_rect(self, rect: QRectF) -> list[PageElement]:
        """Get all elements that intersect with the given rectangle"""
        elements: list[PageElement] = []

        for graphics_item in self.items(rect):
            element = self._item_elements.get(graphics_item)
            if element:
                elements.append(element)

        return elements

    def get_selected_elements(self) -> list[PageElement]:
        """Get all currently selected elements"""
        elements: list[PageElement] = []

        for graphics_item in self.selectedItems():
            element = self._item_elements.get(graphics_item)
            if element:
                elements.append(element)

        return elements

    def select_elements_by_ids(self, element_ids: list[str]) -> None:
        """Select elements by their IDs"""
        # Clear current selection
        self.clearSelection()

        # Select specified elements
        for element_id in element_ids:
            graphics_item = self._element_items.get(element_id)
            if graphics_item:
                graphics_item.setSelected(True)

    def add_stroke_point(self, element_id: str, point: Point) -> bool:
        """Add a point to an existing stroke element"""
        graphics_item = self._element_items.get(element_id)
        if not graphics_item or not isinstance(graphics_item, StrokeGraphicsItem):
            return False

        graphics_item.add_point(point)
        self.element_modified.emit(graphics_item.element)
        self.page_modified.emit()
        return True

    def create_stroke(
        self,
        points: list[Point],
        color: str = "black",
        thickness: float = 2.0,
        tool: str = "pen",
    ) -> Stroke | None:
        """Create a new stroke element and add it to the scene"""
        stroke = Stroke(points=points, color=color, size=thickness, tool=tool)
        graphics_item = self.add_element(stroke)
        return stroke if graphics_item else None

    def create_text(
        self, text: str, position: Point, color: str = "black", size_px: float = 20.0
    ) -> Text | None:
        """Create a new text element and add it to the scene"""
        text_element = Text(text=text, position=position, color=color, size_px=size_px)
        graphics_item = self.add_element(text_element)
        return text_element if graphics_item else None

    def create_image(
        self,
        position: Point,
        width: float,
        height: float,
        image_path: str | None = None,
        image_data: bytes | None = None,
        rotation: float = 0.0,
    ) -> Image | None:
        """Create a new image element and add it to the scene"""
        image = Image(
            position=position,
            width=width,
            height=height,
            image_path=image_path,
            image_data=image_data,
            rotation=rotation,
        )
        graphics_item = self.add_element(image)
        return image if graphics_item else None

    @override
    def drawBackground(self, painter: QPainter | None, rect: QRectF) -> None:
        """Draw the page background with lines"""
        super().drawBackground(painter, rect)

        # Draw notebook lines
        if painter:
            self._draw_notebook_lines(painter, rect)

    def _draw_notebook_lines(self, painter: QPainter, rect: QRectF) -> None:
        """Draw horizontal lines like a notebook page"""
        line_color = QColor(0xDD, 0xCD, 0xC4)

        painter.setPen(QPen(line_color, 1.0))

        # Draw horizontal lines
        y = settings.PAGE_LINES_MARGIN

        while y < settings.PAGE_HEIGHT:
            if (
                settings.PAGE_LINES_MARGIN
                <= y
                <= settings.PAGE_HEIGHT - settings.PAGE_LINES_MARGIN
            ):
                painter.drawLine(
                    QLineF(
                        settings.PAGE_LINES_MARGIN,
                        y,
                        rect.width() - settings.PAGE_LINES_MARGIN,
                        y,
                    )
                )
            y += settings.PAGE_LINES_SPACING

    def get_scene_statistics(self) -> dict[str, int]:
        """Get statistics about the scene contents"""
        stats = {
            "total_elements": len(self._element_items),
            "strokes": 0,
            "texts": 0,
            "images": 0,
            "selected": len(self.selectedItems()),
        }

        for element in self._item_elements.values():
            if isinstance(element, Stroke):
                stats["strokes"] += 1
            elif isinstance(element, Text):
                stats["texts"] += 1
            elif isinstance(element, Image):
                stats["images"] += 1

        return stats

    def export_elements_to_page(self) -> Page:
        """Export all elements to a new Page object"""
        if not self._page:
            self._page = Page()

        # Clear existing elements
        self._page.elements.clear()

        # Add all current elements
        for element in self._item_elements.values():
            self._page.elements.append(element)

        return self._page

    def __len__(self) -> int:
        """Return the number of elements in the scene"""
        return len(self._element_items)

    def __contains__(self, element_id: str) -> bool:
        """Check if an element ID exists in the scene"""
        return element_id in self._element_items

    def __iter__(self):
        """Iterate over all page elements in the scene"""
        return iter(self._item_elements.values())
