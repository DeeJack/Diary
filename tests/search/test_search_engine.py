"""Tests for the search engine"""

import tempfile
import time
from pathlib import Path

from diary.search.search_engine import SearchEngine, SearchFilter, SearchResult
from diary.search.search_index import SearchEntry, SearchIndex
from diary.utils.encryption import SecureEncryption


def _create_test_engine(tmpdir: str) -> SearchEngine:
    """Helper to create a test search engine."""
    salt = SecureEncryption.generate_salt()
    key = SecureEncryption.derive_key("testpass", salt)

    engine = SearchEngine(key, salt)
    engine._index._index_path = Path(tmpdir) / "test_search.db.enc"

    return engine


def _add_entry(engine: SearchEngine, **kwargs) -> None:
    """Helper to add an entry to the engine's index."""
    defaults = {
        "element_id": "elem1",
        "page_id": "page1",
        "notebook_id": "notebook1",
        "element_type": "text",
        "text_content": "test content",
        "bounding_box": None,
    }
    defaults.update(kwargs)

    entry = SearchEntry(
        element_id=defaults["element_id"],
        page_id=defaults["page_id"],
        notebook_id=defaults["notebook_id"],
        element_type=defaults["element_type"],
        text_content=defaults["text_content"],
        bounding_box=defaults["bounding_box"],
        content_hash=SearchIndex.compute_content_hash(defaults["text_content"]),
        last_indexed=time.time(),
    )
    engine._index.add_entry(entry)


class TestSearchEngine:
    """Tests for the SearchEngine class"""

    def test_search_basic(self):
        """Test basic search functionality"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _create_test_engine(tmpdir)
            engine.open()

            _add_entry(engine, element_id="e1", text_content="hello world")
            _add_entry(engine, element_id="e2", text_content="goodbye world")

            results = engine.search("hello")

            assert len(results) == 1
            assert results[0].element_id == "e1"

            engine.close()

    def test_search_with_filter_text_only(self):
        """Test search with text-only filter"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _create_test_engine(tmpdir)
            engine.open()

            _add_entry(
                engine, element_id="e1", element_type="text", text_content="hello text"
            )
            _add_entry(
                engine,
                element_id="e2",
                element_type="stroke",
                text_content="hello stroke",
            )

            results = engine.search("hello", filter_type=SearchFilter.TEXT_ONLY)

            assert len(results) == 1
            assert results[0].element_type == "text"

            engine.close()

    def test_search_with_filter_handwriting_only(self):
        """Test search with handwriting-only filter"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _create_test_engine(tmpdir)
            engine.open()

            _add_entry(
                engine, element_id="e1", element_type="text", text_content="hello text"
            )
            _add_entry(
                engine,
                element_id="e2",
                element_type="stroke",
                text_content="hello stroke",
            )

            results = engine.search("hello", filter_type=SearchFilter.HANDWRITING_ONLY)

            assert len(results) == 1
            assert results[0].element_type == "stroke"

            engine.close()

    def test_search_empty_query(self):
        """Test search with empty query returns empty list"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _create_test_engine(tmpdir)
            engine.open()

            _add_entry(engine, text_content="some content")

            results = engine.search("")
            assert results == []

            results = engine.search("   ")
            assert results == []

            engine.close()

    def test_search_result_has_snippet(self):
        """Test that search results have snippets"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _create_test_engine(tmpdir)
            engine.open()

            _add_entry(engine, text_content="this is a test message")

            results = engine.search("test")

            assert len(results) == 1
            assert results[0].snippet is not None
            assert len(results[0].snippet) > 0

            engine.close()

    def test_search_result_has_relevance_score(self):
        """Test that search results have relevance scores"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _create_test_engine(tmpdir)
            engine.open()

            _add_entry(engine, element_id="e1", text_content="hello world")
            _add_entry(engine, element_id="e2", text_content="hello there")

            results = engine.search("hello")

            assert len(results) == 2
            for result in results:
                assert 0 <= result.relevance_score <= 1

            engine.close()


class TestQueryConversion:
    """Tests for query conversion to FTS5 syntax"""

    def test_convert_simple_term(self):
        """Test converting a simple search term"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _create_test_engine(tmpdir)

            fts_query = engine._convert_to_fts5_query("hello")
            assert "hello*" in fts_query

    def test_convert_multiple_terms(self):
        """Test converting multiple search terms"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _create_test_engine(tmpdir)

            fts_query = engine._convert_to_fts5_query("hello world")
            assert "hello*" in fts_query
            assert "world*" in fts_query

    def test_convert_quoted_phrase(self):
        """Test converting quoted phrases"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _create_test_engine(tmpdir)

            fts_query = engine._convert_to_fts5_query('"hello world"')
            assert '"hello world"' in fts_query

    def test_convert_empty_query(self):
        """Test converting empty query"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _create_test_engine(tmpdir)

            assert engine._convert_to_fts5_query("") == ""
            assert engine._convert_to_fts5_query("   ") == ""


class TestHighlighting:
    """Tests for search result highlighting"""

    def test_highlight_matches(self):
        """Test highlighting matching terms in text"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _create_test_engine(tmpdir)

            highlighted = engine._highlight_matches("hello world", "hello")
            assert "**hello**" in highlighted
            assert "world" in highlighted

    def test_highlight_case_insensitive(self):
        """Test that highlighting is case insensitive"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _create_test_engine(tmpdir)

            highlighted = engine._highlight_matches("Hello World", "hello")
            assert "**Hello**" in highlighted

    def test_highlight_multiple_terms(self):
        """Test highlighting multiple terms"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _create_test_engine(tmpdir)

            highlighted = engine._highlight_matches("hello world foo bar", "hello bar")
            assert "**hello**" in highlighted
            assert "**bar**" in highlighted


class TestSearchResult:
    """Tests for SearchResult dataclass"""

    def test_from_entry(self):
        """Test creating SearchResult from SearchEntry"""
        entry = SearchEntry(
            element_id="elem1",
            page_id="page1",
            notebook_id="notebook1",
            element_type="text",
            text_content="test content here",
            bounding_box=None,
            content_hash="abc123",
            last_indexed=time.time(),
        )

        result = SearchResult.from_entry(entry)

        assert result.element_id == "elem1"
        assert result.page_id == "page1"
        assert result.notebook_id == "notebook1"
        assert result.element_type == "text"
        assert result.matched_text == "test content here"
        assert result.snippet == "test content here"

    def test_from_entry_with_bounding_box(self):
        """Test creating SearchResult from entry with bounding box"""
        entry = SearchEntry(
            element_id="elem1",
            page_id="page1",
            notebook_id="notebook1",
            element_type="stroke",
            text_content="handwritten text",
            bounding_box='{"x": 10, "y": 20, "w": 100, "h": 50}',
            content_hash="abc123",
            last_indexed=time.time(),
        )

        result = SearchResult.from_entry(entry)

        assert result.bounding_box is not None
        assert result.bounding_box["x"] == 10
        assert result.bounding_box["y"] == 20

    def test_from_entry_long_text_truncated(self):
        """Test that long text is truncated in snippet"""
        long_text = "a" * 200
        entry = SearchEntry(
            element_id="elem1",
            page_id="page1",
            notebook_id="notebook1",
            element_type="text",
            text_content=long_text,
            bounding_box=None,
            content_hash="abc123",
            last_indexed=time.time(),
        )

        result = SearchResult.from_entry(entry)

        assert len(result.snippet) < len(long_text)
        assert result.snippet.endswith("...")
