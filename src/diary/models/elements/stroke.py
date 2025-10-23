"""Represents a continuous Stroke of ink in the Page"""

from dataclasses import dataclass
import math
from typing import override, Any, cast

from diary.config import settings
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
            settings.SERIALIZATION_KEYS.ELEMENT_TYPE.value: self.element_type,
            settings.SERIALIZATION_KEYS.ELEMENT_ID.value: self.element_id,
            settings.SERIALIZATION_KEYS.POINTS.value: [
                p.to_dict() for p in self.points
            ],
            settings.SERIALIZATION_KEYS.COLOR.value: self.color,
            settings.SERIALIZATION_KEYS.THICKNESS.value: float(f"{self.thickness:.1f}"),
            settings.SERIALIZATION_KEYS.TOOL.value: self.tool,
        }

    @classmethod
    @override
    def from_dict(cls, data: dict[str, Any]) -> "Stroke":
        """Deserialize this stroke from a dictionary loaded from JSON"""
        points: list[Point] = []
        if settings.SERIALIZATION_KEYS.POINTS.value in data and isinstance(
            data[settings.SERIALIZATION_KEYS.POINTS.value], list
        ):
            for point_data in data[settings.SERIALIZATION_KEYS.POINTS.value]:
                if isinstance(point_data, (tuple, list)):
                    point = Point(
                        x=float(point_data[0]),
                        y=float(point_data[1]),
                        pressure=float(point_data[2]),
                    )
                    points.append(point)

        return cls(
            points=points,
            color=cast(str, data.get(settings.SERIALIZATION_KEYS.COLOR.value, "black")),
            size=float(data.get(settings.SERIALIZATION_KEYS.THICKNESS.value, 1.0)),
            tool=cast(str, data.get(settings.SERIALIZATION_KEYS.TOOL.value, "pen")),
            element_id=data.get(settings.SERIALIZATION_KEYS.ELEMENT_ID.value),
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
