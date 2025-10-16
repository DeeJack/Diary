from dataclasses import dataclass
import time
from typing import override
import uuid

from diary.models.stroke import Stroke


@dataclass
class Page:
    def __init__(
        self,
        strokes: list[Stroke] | None = None,
        created_at: float | None = None,
        page_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ):
        self.strokes: list[Stroke] = strokes if strokes is not None else []
        self.created_at: float = created_at or time.time()
        self.page_id: str = page_id or uuid.uuid4().hex
        self.metadata: dict[str, object] = metadata if metadata is not None else {}

    @override
    def __str__(self) -> str:
        return f"Page(Strokes={self.strokes}; Created at={self.created_at}; Page ID={self.page_id}; Metadata={self.metadata})"
