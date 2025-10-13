from pathlib import Path

from diary.models.page import Page


class PageDAO:
    def save(self, page: Page, filepath: Path):
        pass

    def load(self, filepath: Path):
        pass
