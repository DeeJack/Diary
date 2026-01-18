"""
Search module for the Diary application.

Provides OCR-based handwriting search and text search with encrypted FTS5 index.
"""

from diary.search.index_manager import IndexManager
from diary.search.search_engine import SearchEngine, SearchFilter, SearchResult
from diary.search.search_index import SearchEntry, SearchIndex
from diary.search.stroke_rasterizer import BoundingBox, StrokeGroup, StrokeRasterizer

__all__ = [
    "BoundingBox",
    "IndexManager",
    "SearchEngine",
    "SearchEntry",
    "SearchFilter",
    "SearchIndex",
    "SearchResult",
    "StrokeGroup",
    "StrokeRasterizer",
]
