from dataclasses import dataclass

from diary.models.point import Point


@dataclass
class Stroke:
    """
    Represents a stroke of the pen: a set of points drawn without lifting the pen.
    """

    def __init__(self, points: list[Point], color: str, size: float, tool: str = "pen"):
        self.points: list[Point] = points
        self.color: str = color
        self.thickness: float = size
        self.tool: str = tool
