from dataclasses import dataclass
from diary.models.page import Page


@dataclass
class Notebook:
    def __init__(self, pages: list[Page] | None = None):
        self.pages: list[Page] = pages or []
