"""Tests for the search index"""

import tempfile
import time
from pathlib import Path

from diary.search.search_index import SearchEntry, SearchIndex
from diary.utils.encryption import SecureBuffer, SecureEncryption


def _create_test_index(tmpdir: str) -> tuple[SearchIndex, SecureBuffer, bytes]:
    """Helper to create a test search index."""
    salt = SecureEncryption.generate_salt()
    key = SecureEncryption.derive_key("testpass", salt)

    # Override the index path for testing
    index = SearchIndex(key, salt)
    index._index_path = Path(tmpdir) / "test_search.db.enc"

    return index, key, salt


def _create_test_entry(
    element_id: str = "elem1",
    page_id: str = "page1",
    notebook_id: str = "notebook1",
    element_type: str = "text",
    text_content: str = "test content",
) -> SearchEntry:
    """Helper to create a test search entry."""
    return SearchEntry(
        element_id=element_id,
        page_id=page_id,
        notebook_id=notebook_id,
        element_type=element_type,
        text_content=text_content,
        bounding_box=None,
        content_hash=SearchIndex.compute_content_hash(text_content),
        last_indexed=time.time(),
    )


class TestSearchIndex:
    """Tests for the SearchIndex class"""

    def test_open_and_close(self):
        """Test opening and closing the index"""
        with tempfile.TemporaryDirectory() as tmpdir:
            index, _, _ = _create_test_index(tmpdir)

            index.open()
            assert index._conn is not None

            index.close()
            assert index._conn is None

    def test_add_entry(self):
        """Test adding an entry to the index"""
        with tempfile.TemporaryDirectory() as tmpdir:
            index, _, _ = _create_test_index(tmpdir)
            index.open()

            entry = _create_test_entry()
            index.add_entry(entry)

            retrieved = index.get_entry(entry.element_id)
            assert retrieved is not None
            assert retrieved.element_id == entry.element_id
            assert retrieved.text_content == entry.text_content

            index.close()

    def test_update_entry(self):
        """Test updating an existing entry"""
        with tempfile.TemporaryDirectory() as tmpdir:
            index, _, _ = _create_test_index(tmpdir)
            index.open()

            entry = _create_test_entry(text_content="original content")
            index.add_entry(entry)

            # Update with new content
            updated = _create_test_entry(text_content="updated content")
            index.add_entry(updated)

            retrieved = index.get_entry(entry.element_id)
            assert retrieved.text_content == "updated content"

            index.close()

    def test_remove_entry(self):
        """Test removing an entry from the index"""
        with tempfile.TemporaryDirectory() as tmpdir:
            index, _, _ = _create_test_index(tmpdir)
            index.open()

            entry = _create_test_entry()
            index.add_entry(entry)
            index.remove_entry(entry.element_id)

            retrieved = index.get_entry(entry.element_id)
            assert retrieved is None

            index.close()

    def test_remove_page_entries(self):
        """Test removing all entries for a page"""
        with tempfile.TemporaryDirectory() as tmpdir:
            index, _, _ = _create_test_index(tmpdir)
            index.open()

            entry1 = _create_test_entry(
                element_id="e1", page_id="page1", text_content="text one"
            )
            entry2 = _create_test_entry(
                element_id="e2", page_id="page1", text_content="text two"
            )
            entry3 = _create_test_entry(
                element_id="e3", page_id="page2", text_content="text three"
            )

            index.add_entry(entry1)
            index.add_entry(entry2)
            index.add_entry(entry3)

            index.remove_page_entries("page1")

            assert index.get_entry("e1") is None
            assert index.get_entry("e2") is None
            assert index.get_entry("e3") is not None

            index.close()

    def test_search_basic(self):
        """Test basic FTS5 search"""
        with tempfile.TemporaryDirectory() as tmpdir:
            index, _, _ = _create_test_index(tmpdir)
            index.open()

            index.add_entry(
                _create_test_entry(
                    element_id="e1", text_content="hello world"
                )
            )
            index.add_entry(
                _create_test_entry(
                    element_id="e2", text_content="goodbye world"
                )
            )

            results = index.search("hello")

            assert len(results) == 1
            assert results[0].element_id == "e1"

            index.close()

    def test_search_multiple_matches(self):
        """Test search returning multiple matches"""
        with tempfile.TemporaryDirectory() as tmpdir:
            index, _, _ = _create_test_index(tmpdir)
            index.open()

            index.add_entry(
                _create_test_entry(element_id="e1", text_content="hello world")
            )
            index.add_entry(
                _create_test_entry(element_id="e2", text_content="goodbye world")
            )

            results = index.search("world")

            assert len(results) == 2

            index.close()

    def test_search_by_element_type(self):
        """Test filtering search by element type"""
        with tempfile.TemporaryDirectory() as tmpdir:
            index, _, _ = _create_test_index(tmpdir)
            index.open()

            index.add_entry(
                _create_test_entry(
                    element_id="e1", element_type="text", text_content="hello world"
                )
            )
            index.add_entry(
                _create_test_entry(
                    element_id="e2", element_type="stroke", text_content="hello there"
                )
            )

            results = index.search("hello", element_types=["text"])

            assert len(results) == 1
            assert results[0].element_id == "e1"

            index.close()

    def test_search_by_notebook(self):
        """Test filtering search by notebook ID"""
        with tempfile.TemporaryDirectory() as tmpdir:
            index, _, _ = _create_test_index(tmpdir)
            index.open()

            index.add_entry(
                _create_test_entry(
                    element_id="e1", notebook_id="nb1", text_content="hello world"
                )
            )
            index.add_entry(
                _create_test_entry(
                    element_id="e2", notebook_id="nb2", text_content="hello there"
                )
            )

            results = index.search("hello", notebook_id="nb1")

            assert len(results) == 1
            assert results[0].element_id == "e1"

            index.close()

    def test_search_empty_query(self):
        """Test search with empty query returns no results"""
        with tempfile.TemporaryDirectory() as tmpdir:
            index, _, _ = _create_test_index(tmpdir)
            index.open()

            index.add_entry(_create_test_entry(text_content="hello world"))

            results = index.search("")
            assert len(results) == 0

            index.close()

    def test_persistence(self):
        """Test that index persists across open/close cycles"""
        with tempfile.TemporaryDirectory() as tmpdir:
            salt = SecureEncryption.generate_salt()
            key = SecureEncryption.derive_key("testpass", salt)
            index_path = Path(tmpdir) / "test_search.db.enc"

            # Create and populate index
            index1 = SearchIndex(key, salt)
            index1._index_path = index_path
            index1.open()
            index1.add_entry(_create_test_entry(text_content="persistent data"))
            index1.close()

            # Reopen and verify data
            index2 = SearchIndex(key, salt)
            index2._index_path = index_path
            index2.open()

            results = index2.search("persistent")
            assert len(results) == 1
            assert results[0].text_content == "persistent data"

            index2.close()

    def test_get_content_hash(self):
        """Test getting content hash for change detection"""
        with tempfile.TemporaryDirectory() as tmpdir:
            index, _, _ = _create_test_index(tmpdir)
            index.open()

            entry = _create_test_entry(text_content="test content")
            index.add_entry(entry)

            hash_val = index.get_content_hash(entry.element_id)
            assert hash_val is not None
            assert hash_val == entry.content_hash

            index.close()

    def test_get_indexed_element_ids(self):
        """Test getting all indexed element IDs for a page"""
        with tempfile.TemporaryDirectory() as tmpdir:
            index, _, _ = _create_test_index(tmpdir)
            index.open()

            index.add_entry(
                _create_test_entry(element_id="e1", page_id="page1")
            )
            index.add_entry(
                _create_test_entry(element_id="e2", page_id="page1")
            )
            index.add_entry(
                _create_test_entry(element_id="e3", page_id="page2")
            )

            ids = index.get_indexed_element_ids("page1")

            assert len(ids) == 2
            assert "e1" in ids
            assert "e2" in ids
            assert "e3" not in ids

            index.close()

    def test_get_stats(self):
        """Test getting index statistics"""
        with tempfile.TemporaryDirectory() as tmpdir:
            index, _, _ = _create_test_index(tmpdir)
            index.open()

            index.add_entry(
                _create_test_entry(element_id="e1", element_type="text")
            )
            index.add_entry(
                _create_test_entry(element_id="e2", element_type="text")
            )
            index.add_entry(
                _create_test_entry(element_id="e3", element_type="stroke")
            )

            stats = index.get_stats()

            assert stats["total_entries"] == 3
            assert stats["text_entries"] == 2
            assert stats["stroke_entries"] == 1

            index.close()


class TestContentHash:
    """Tests for content hashing"""

    def test_compute_content_hash(self):
        """Test content hash computation"""
        hash1 = SearchIndex.compute_content_hash("hello world")
        hash2 = SearchIndex.compute_content_hash("hello world")
        hash3 = SearchIndex.compute_content_hash("different content")

        assert hash1 == hash2
        assert hash1 != hash3
        assert len(hash1) == 16  # Truncated to 16 chars

    def test_hash_is_deterministic(self):
        """Test that hashing is deterministic"""
        content = "test content for hashing"
        hashes = [SearchIndex.compute_content_hash(content) for _ in range(100)]
        assert all(h == hashes[0] for h in hashes)
