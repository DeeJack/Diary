"""UI adapters for dynamically rendering different types of page elements"""

from abc import ABC, abstractmethod

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QPainter

from diary.models.page_element import PageElement


class ElementAdapter(ABC):
    """Abstract base class for rendering page elements with QPainter"""

    @abstractmethod
    def render(self, element: PageElement, painter: QPainter) -> None:
        """Render the given element using the provided QPainter"""

    @abstractmethod
    def can_handle(self, element: PageElement) -> bool:
        """Check if this adapter can handle the given element type"""

    @abstractmethod
    def rect(self, element: PageElement) -> QRectF:
        """Bounding rect for the element"""


class AdapterRegistry:
    """Registry for managing element adapters"""

    def __init__(self):
        self._adapters: list[ElementAdapter] = []

    def register(self, adapter: ElementAdapter) -> None:
        """Register a new adapter"""
        self._adapters.append(adapter)

    def get_adapter(self, element: PageElement) -> ElementAdapter:
        """Get the appropriate adapter for the given element"""
        for adapter in self._adapters:
            if adapter.can_handle(element):
                return adapter
        raise ValueError("Couldn't find adapter for element %s", element.element_id)

    def render_element(self, element: PageElement, painter: QPainter) -> bool:
        """Render an element using the appropriate adapter"""
        adapter = self.get_adapter(element)
        if adapter:
            adapter.render(element, painter)
            return True
        return False


# Global registry instance
adapter_registry = AdapterRegistry()
