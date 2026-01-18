"""
Encrypted SQLite FTS5 search index for the Diary application.

Stores indexed text content with full-text search capabilities.
The database is encrypted at rest using the same key as the notebook.
"""

import hashlib
import logging
import sqlite3
from dataclasses import dataclass

from diary.config import settings
from diary.utils.encryption import SecureBuffer, SecureEncryption


@dataclass
class SearchEntry:
    """Represents a single indexed entry in the search database."""

    element_id: str
    page_id: str
    notebook_id: str
    element_type: str  # "text", "stroke", "voice_memo"
    text_content: str
    bounding_box: str | None  # JSON string for strokes: {"x":..,"y":..,"w":..,"h":..}
    content_hash: str  # For change detection
    last_indexed: float  # Timestamp


class SearchIndex:
    """
    Encrypted SQLite FTS5 search index.

    The index is stored encrypted on disk and decrypted into memory
    when opened. Changes are encrypted before writing back to disk.
    """

    MAGIC: bytes = b"SRCHIDX1"
    VERSION: int = 1

    def __init__(self, key_buffer: SecureBuffer, salt: bytes):
        """
        Initialize the search index.

        Args:
            key_buffer: Encryption key derived from user password
            salt: Salt used for key derivation
        """
        self.key_buffer = key_buffer
        self.salt = salt
        self.logger = logging.getLogger("SearchIndex")
        self._conn: sqlite3.Connection | None = None
        self._index_path = settings.SEARCH_INDEX_PATH

    def open(self) -> None:
        """
        Open the search index, loading from disk if it exists.

        Creates an in-memory SQLite database with FTS5 support.
        If an encrypted index file exists, it's decrypted and loaded.
        """
        if self._conn is not None:
            return

        # Create in-memory database
        self._conn = sqlite3.connect(":memory:")
        self._conn.row_factory = sqlite3.Row

        # Load existing index if it exists, otherwise create fresh schema
        if self._index_path.exists():
            try:
                self._load_from_disk()
                self.logger.debug("Loaded search index from disk")
            except (ValueError, sqlite3.Error) as e:
                self.logger.warning("Failed to load search index: %s", e)
                # Recreate schema on failure
                self._conn.close()
                self._conn = sqlite3.connect(":memory:")
                self._conn.row_factory = sqlite3.Row
                self._create_schema()
        else:
            self._create_schema()

    def close(self, save: bool = True) -> None:
        """Close the search index, optionally saving to disk."""
        if self._conn is not None:
            if save:
                self._save_to_disk()
            self._conn.close()
            self._conn = None

    def _create_schema(self) -> None:
        """Create the FTS5 schema and metadata table."""
        if self._conn is None:
            return

        cursor = self._conn.cursor()

        # Create FTS5 virtual table for full-text search
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
                text_content,
                element_id UNINDEXED,
                tokenize='porter unicode61'
            )
        """)

        # Create metadata table for entries
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_entries (
                element_id TEXT PRIMARY KEY,
                page_id TEXT NOT NULL,
                notebook_id TEXT NOT NULL,
                element_type TEXT NOT NULL,
                bounding_box TEXT,
                content_hash TEXT NOT NULL,
                last_indexed REAL NOT NULL
            )
        """)

        # Create indices for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_page_id ON search_entries(page_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_notebook_id ON search_entries(notebook_id)
        """)

        self._conn.commit()

    def _load_from_disk(self) -> None:
        """Load and decrypt the index from disk."""
        import json

        if not self._index_path.exists():
            return

        # Decrypt the file
        decrypted_data = SecureEncryption.decrypt_file(
            self._index_path, self.key_buffer
        )

        # Verify magic bytes
        if not decrypted_data.startswith(self.MAGIC):
            raise ValueError("Invalid search index format")

        # Extract JSON data after magic bytes
        json_data = decrypted_data[len(self.MAGIC) :].decode("utf-8")
        data = json.loads(json_data)

        # Create schema first
        self._create_schema()

        # Restore entries
        if self._conn is not None:
            cursor = self._conn.cursor()
            for entry_data in data.get("entries", []):
                # Insert into metadata table
                cursor.execute(
                    """
                    INSERT INTO search_entries
                    (element_id, page_id, notebook_id, element_type, bounding_box, content_hash, last_indexed)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry_data["element_id"],
                        entry_data["page_id"],
                        entry_data["notebook_id"],
                        entry_data["element_type"],
                        entry_data["bounding_box"],
                        entry_data["content_hash"],
                        entry_data["last_indexed"],
                    ),
                )
                # Insert into FTS table
                cursor.execute(
                    "INSERT INTO search_fts (text_content, element_id) VALUES (?, ?)",
                    (entry_data["text_content"], entry_data["element_id"]),
                )
            self._conn.commit()

    def _save_to_disk(self) -> None:
        """Encrypt and save the index to disk."""
        import json

        if self._conn is None:
            return

        cursor = self._conn.cursor()

        # Export all entries as JSON (FTS5 doesn't work well with iterdump)
        cursor.execute(
            """
            SELECT e.*, f.text_content
            FROM search_entries e
            JOIN search_fts f ON e.element_id = f.element_id
            """
        )

        entries = []
        for row in cursor.fetchall():
            entries.append(
                {
                    "element_id": row["element_id"],
                    "page_id": row["page_id"],
                    "notebook_id": row["notebook_id"],
                    "element_type": row["element_type"],
                    "bounding_box": row["bounding_box"],
                    "content_hash": row["content_hash"],
                    "last_indexed": row["last_indexed"],
                    "text_content": row["text_content"],
                }
            )

        data = {"version": self.VERSION, "entries": entries}
        json_data = json.dumps(data)

        # Prepend magic bytes
        file_data = self.MAGIC + json_data.encode("utf-8")

        # Ensure parent directory exists
        self._index_path.parent.mkdir(parents=True, exist_ok=True)

        # Encrypt and write
        SecureEncryption.encrypt_bytes_to_file(
            file_data, self._index_path, self.key_buffer, self.salt
        )
        self.logger.debug("Saved search index to disk")

    def add_entry(self, entry: SearchEntry) -> None:
        """
        Add or update an entry in the search index.

        Args:
            entry: SearchEntry to add or update
        """
        if self._conn is None:
            self.open()

        cursor = self._conn.cursor()  # pyright: ignore[reportOptionalMemberAccess]

        # Check if entry already exists
        cursor.execute(
            "SELECT content_hash FROM search_entries WHERE element_id = ?",
            (entry.element_id,),
        )
        existing = cursor.fetchone()

        if existing:
            # Update existing entry if content changed
            if existing["content_hash"] != entry.content_hash:
                # Remove from FTS
                cursor.execute(
                    "DELETE FROM search_fts WHERE element_id = ?", (entry.element_id,)
                )
                # Update metadata
                cursor.execute(
                    """
                    UPDATE search_entries SET
                        page_id = ?,
                        notebook_id = ?,
                        element_type = ?,
                        bounding_box = ?,
                        content_hash = ?,
                        last_indexed = ?
                    WHERE element_id = ?
                    """,
                    (
                        entry.page_id,
                        entry.notebook_id,
                        entry.element_type,
                        entry.bounding_box,
                        entry.content_hash,
                        entry.last_indexed,
                        entry.element_id,
                    ),
                )
                # Add to FTS
                cursor.execute(
                    "INSERT INTO search_fts (text_content, element_id) VALUES (?, ?)",
                    (entry.text_content, entry.element_id),
                )
        else:
            # Insert new entry
            cursor.execute(
                """
                INSERT INTO search_entries
                (element_id, page_id, notebook_id, element_type, bounding_box, content_hash, last_indexed)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.element_id,
                    entry.page_id,
                    entry.notebook_id,
                    entry.element_type,
                    entry.bounding_box,
                    entry.content_hash,
                    entry.last_indexed,
                ),
            )
            cursor.execute(
                "INSERT INTO search_fts (text_content, element_id) VALUES (?, ?)",
                (entry.text_content, entry.element_id),
            )

        self._conn.commit()  # pyright: ignore[reportOptionalMemberAccess]

    def remove_entry(self, element_id: str) -> None:
        """Remove an entry from the search index."""
        if self._conn is None:
            return

        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM search_fts WHERE element_id = ?", (element_id,))
        cursor.execute("DELETE FROM search_entries WHERE element_id = ?", (element_id,))
        self._conn.commit()

    def remove_page_entries(self, page_id: str) -> None:
        """Remove all entries for a specific page."""
        if self._conn is None:
            return

        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT element_id FROM search_entries WHERE page_id = ?", (page_id,)
        )
        element_ids = [row["element_id"] for row in cursor.fetchall()]

        for element_id in element_ids:
            cursor.execute("DELETE FROM search_fts WHERE element_id = ?", (element_id,))
        cursor.execute("DELETE FROM search_entries WHERE page_id = ?", (page_id,))
        self._conn.commit()

    def get_entry(self, element_id: str) -> SearchEntry | None:
        """Get a specific entry by element ID."""
        if self._conn is None:
            return None

        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT e.*, f.text_content
            FROM search_entries e
            JOIN search_fts f ON e.element_id = f.element_id
            WHERE e.element_id = ?
            """,
            (element_id,),
        )
        row = cursor.fetchone()
        if row:
            return SearchEntry(
                element_id=row["element_id"],
                page_id=row["page_id"],
                notebook_id=row["notebook_id"],
                element_type=row["element_type"],
                text_content=row["text_content"],
                bounding_box=row["bounding_box"],
                content_hash=row["content_hash"],
                last_indexed=row["last_indexed"],
            )
        return None

    def get_content_hash(self, element_id: str) -> str | None:
        """Get the content hash for an element, for change detection."""
        if self._conn is None:
            return None

        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT content_hash FROM search_entries WHERE element_id = ?",
            (element_id,),
        )
        row = cursor.fetchone()
        return row["content_hash"] if row else None

    def search(
        self,
        query: str,
        element_types: list[str] | None = None,
        notebook_id: str | None = None,
        limit: int = 50,
    ) -> list[SearchEntry]:
        """
        Search the index using FTS5.

        Args:
            query: Search query (supports FTS5 syntax)
            element_types: Filter by element types (e.g., ["text", "stroke"])
            notebook_id: Filter by notebook ID
            limit: Maximum number of results

        Returns:
            List of matching SearchEntry objects
        """
        if self._conn is None:
            return []

        cursor = self._conn.cursor()

        # Build query with filters
        sql = """
            SELECT e.*, f.text_content,
                   bm25(search_fts) as rank
            FROM search_fts f
            JOIN search_entries e ON f.element_id = e.element_id
            WHERE search_fts MATCH ?
        """
        params: list[str | int] = [query]

        if element_types:
            placeholders = ",".join("?" * len(element_types))
            sql += f" AND e.element_type IN ({placeholders})"
            params.extend(element_types)

        if notebook_id:
            sql += " AND e.notebook_id = ?"
            params.append(notebook_id)

        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)

        try:
            cursor.execute(sql, params)
            results: list[SearchEntry] = []
            for row in cursor.fetchall():
                results.append(
                    SearchEntry(
                        element_id=row["element_id"],
                        page_id=row["page_id"],
                        notebook_id=row["notebook_id"],
                        element_type=row["element_type"],
                        text_content=row["text_content"],
                        bounding_box=row["bounding_box"],
                        content_hash=row["content_hash"],
                        last_indexed=row["last_indexed"],
                    )
                )
            return results
        except sqlite3.OperationalError as e:
            self.logger.warning("Search query error: %s", e)
            return []

    def get_indexed_element_ids(
        self, page_id: str, element_types: list[str] | None = None
    ) -> set[str]:
        """Get indexed element IDs for a page, optionally filtered by type."""
        if self._conn is None:
            return set()

        cursor = self._conn.cursor()
        sql = "SELECT element_id FROM search_entries WHERE page_id = ?"
        params: list[str] = [page_id]
        if element_types:
            placeholders = ",".join("?" * len(element_types))
            sql += f" AND element_type IN ({placeholders})"
            params.extend(element_types)
        cursor.execute(sql, params)
        return {row["element_id"] for row in cursor.fetchall()}

    def get_stats(self) -> dict[str, int]:
        """Get statistics about the search index."""
        if self._conn is None:
            return {"total_entries": 0, "text_entries": 0, "stroke_entries": 0}

        cursor = self._conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM search_entries")
        total = cursor.fetchone()["count"]

        cursor.execute(
            "SELECT element_type, COUNT(*) as count FROM search_entries GROUP BY element_type"
        )
        by_type = {row["element_type"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_entries": total,
            "text_entries": by_type.get("text", 0),
            "stroke_entries": by_type.get("stroke", 0),
            "voice_memo_entries": by_type.get("voice_memo", 0),
        }

    @staticmethod
    def compute_content_hash(content: str) -> str:
        """Compute a hash of content for change detection."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
