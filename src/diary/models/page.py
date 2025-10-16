from dataclasses import dataclass
import time
import uuid

from diary.models.stroke import Stroke


@dataclass
class Page:
    def __init__(
        self,
        strokes: list[Stroke] | None = None,
        created_at: float = time.time(),
        page_id: str = uuid.uuid4().hex,
        metadata: dict | None = None,
    ):
        self.strokes: list[Stroke] = strokes if strokes is not None else []
        self.created_at: float = created_at
        self.page_id: str = page_id
        self.metadata: dict = metadata if metadata is not None else {}
