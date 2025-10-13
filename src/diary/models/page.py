from dataclasses import dataclass
import time
import uuid

from diary.models.stroke import Stroke


@dataclass
class Page:
    def __init__(
        self,
        strokes: list[Stroke],
        created_at: float = time.time(),
        page_id: str = uuid.uuid4().hex,
        metadata: dict = {},
    ):
        self.strokes: list[Stroke] = strokes
        self.created_at: float = created_at
        self.page_id: str = page_id
        self.metadata: dict = metadata
