"""Represents a Point for the ink inside a Page"""

from dataclasses import dataclass


@dataclass()
class Point:
    """Represents a Point for ink in the page"""

    def __init__(self, x: float, y: float, pressure: float = 1.0):
        self.x: float = x
        self.y: float = y
        self.pressure: float = pressure

    @classmethod
    def from_dict(cls, data: list[float]):
        """Create Point from: [x, y, pressure]"""
        x, y, pressure = data
        return cls(x, y, pressure)

    def to_dict(self):
        """Serialize to [x, y, pressure]"""
        return [
            float(f"{self.x:.1f}"),
            float(f"{self.y:.1f}"),
            float(f"{self.pressure:.1f}"),
        ]
