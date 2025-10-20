"""Represents a continuous Stroke of ink in the Page"""

from dataclasses import dataclass
import math
from typing import override, Any, cast

from diary.models.point import Point
from diary.models.page_element import PageElement


@dataclass
class Stroke(PageElement):
    """Represents a continuous Stroke of ink in the Page"""

    def __init__(
        self,
        points: list[Point] | None = None,
        color: str = "black",
        size: float = 1,
        tool: str = "pen",
        element_id: str | None = None,
    ):
        super().__init__("stroke", element_id)
        self.points: list[Point] = points if points is not None else []
        self.color: str = color
        self.thickness: float = size
        self.tool: str = tool

    @override
    def intersects(self, pos: Point, radius: float) -> bool:
        for point in self.points:
            distance = math.sqrt((point.x - pos.x) ** 2 + (point.y - pos.y) ** 2)
            if distance <= radius:
                return True
        return False

    @override
    def to_dict(self) -> dict[str, Any]:
        """Serialize this stroke to a dictionary for JSON storage"""
        return {
            "element_type": self.element_type,
            "element_id": self.element_id,
            "points": [
                {"x": p.x, "y": p.y, "pressure": p.pressure} for p in self.points
            ],
            "color": self.color,
            "thickness": self.thickness,
            "tool": self.tool,
        }

    @classmethod
    @override
    def from_dict(cls, data: dict[str, Any]) -> "Stroke":
        """Deserialize this stroke from a dictionary loaded from JSON"""
        points: list[Point] = []
        if "points" in data and isinstance(data["points"], list):
            for point_data in data["points"]:
                if isinstance(point_data, dict):
                    point = Point(
                        x=cast(float, point_data.get("x", 0.0)),
                        y=cast(float, point_data.get("y", 0.0)),
                        pressure=cast(float, point_data.get("pressure", 1.0)),
                    )
                    points.append(point)

        return cls(
            points=points,
            color=cast(str, data.get("color", "black")),
            size=cast(float, data.get("thickness", 1.0)),
            tool=cast(str, data.get("tool", "pen")),
            element_id=data.get("element_id"),
        )

    @override
    def __eq__(self, other: object, /) -> bool:
        if not isinstance(other, Stroke):
            return NotImplemented

        parent_result = super().__eq__(other)  # Check for ID
        if parent_result is not NotImplemented:
            return parent_result

        return (
            self.element_type == other.element_type
            and len(self.points) == len(other.points)
            and self.color == other.color
            and self.thickness == other.thickness
            and self.tool == other.tool
            and self.points == other.points
        )
