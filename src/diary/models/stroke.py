"""Represents a continuous Stroke of ink in the Page"""

from dataclasses import dataclass
import math
from typing import override

from diary.models.point import Point


@dataclass
class Stroke:
    """Represents a continuous Stroke of ink in the Page"""

    def __init__(
        self,
        points: list[Point] | None = None,
        color: str = "black",
        size: float = 1,
        tool: str = "pen",
    ):
        self.points: list[Point] = points if points is not None else []
        self.color: str = color
        self.thickness: float = size
        self.tool: str = tool

    def intersects(self, pos: Point, radius: float) -> bool:
        for point in self.points:
            distance = math.sqrt((point.x - pos.x) ** 2 + (point.y - pos.y) ** 2)
            if distance <= radius:
                return True
        return False

    @override
    def __eq__(self, value: object, /) -> bool:
        if not value or not isinstance(value, Stroke):
            return False
        return (
            len(self.points) == len(value.points)
            and self.color == value.color
            and self.thickness == value.thickness
            and self.tool == value.tool
            and self.points == value.points
        )
