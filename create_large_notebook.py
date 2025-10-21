from pathlib import Path
from random import randint
import secrets
from diary.models import Notebook, NotebookDAO, Page, PageElement, Point, Stroke
from diary.utils.encryption import SecureEncryption


def create_large_notebook():
    NUM_PAGES = 100
    STROKES_PER_PAGE = 50
    MAX_POINTS_PER_STROKE = 100

    notebook = Notebook()

    for _ in range(NUM_PAGES):
        strokes: list[PageElement] = []
        for _ in range(STROKES_PER_PAGE):
            points: list[Point] = []
            for _ in range(randint(0, MAX_POINTS_PER_STROKE)):
                points.append(Point(randint(0, 800), randint(0, 1100), 1.0))
            strokes.append(Stroke(points=points))
        notebook.pages.append(Page(elements=strokes))

    salt = secrets.token_bytes(SecureEncryption.SALT_SIZE)
    key_buffer = SecureEncryption.derive_key("test", salt)

    NotebookDAO.save(notebook, Path("data/test_notebook.enc"), key_buffer, salt)


create_large_notebook()
