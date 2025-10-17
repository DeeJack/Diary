"""Represents a Point for the ink inside a Page"""

from dataclasses import dataclass


@dataclass()
class Point:
    """Represents a Point for ink in the page"""

    def __init__(self, x: float, y: float, pressure: float):
        self.x: float = x
        self.y: float = y
        self.pressure: float = pressure
