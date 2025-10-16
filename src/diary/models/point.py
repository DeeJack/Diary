from dataclasses import dataclass


@dataclass
class Point:
    def __init__(self, x: float, y: float, pressure: float):
        self.x: float = x
        self.y: float = y
        self.pressure: float = pressure
