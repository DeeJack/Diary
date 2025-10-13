from dataclasses import dataclass


@dataclass
class Point:
    def __init__(self, x: int, y: int, pressure: float):
        self.x: int = x
        self.y: int = y
        self.pressure: float = pressure
