"""Represents a continuous Stroke of ink in the Page"""

from dataclasses import dataclass

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
