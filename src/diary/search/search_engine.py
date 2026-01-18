"""
Search Engine - Query processing and result presentation.

Converts user queries to FTS5 syntax and returns ranked results.
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum

from diary.config import settings
from diary.search.search_index import SearchEntry, SearchIndex
from diary.utils.encryption import SecureBuffer


class SearchFilter(Enum):
    """Filter options for search results."""

    ALL = "all"
    TEXT_ONLY = "text"
    HANDWRITING_ONLY = "stroke"
    VOICE_ONLY = "voice_memo"


@dataclass
class SearchResult:
    """Represents a single search result for UI display."""

    element_id: str
    page_id: str
    notebook_id: str
    element_type: str
    matched_text: str
    snippet: str  # Text snippet with context
    relevance_score: float
    bounding_box: dict[str, float] | None  # For highlighting strokes

    @staticmethod
    def from_entry(entry: SearchEntry) -> "SearchResult":
        """Create a SearchResult from a SearchEntry."""
        import json

        bounding_box = None
        if entry.bounding_box:
            try:
                bounding_box = json.loads(entry.bounding_box)
            except json.JSONDecodeError:
                pass

        # Create a snippet from the text content
        text = entry.text_content
        snippet_length = settings.SEARCH_SNIPPET_LENGTH
        snippet = text[:snippet_length] + "..." if len(text) > snippet_length else text

        return SearchResult(
            element_id=entry.element_id,
            page_id=entry.page_id,
            notebook_id=entry.notebook_id,
            element_type=entry.element_type,
            matched_text=text,
            snippet=snippet,
            relevance_score=0.0,  # Will be set by search
            bounding_box=bounding_box,
        )


class SearchEngine:
    """
    Handles search queries and result presentation.

    Converts user-friendly queries to FTS5 syntax and
    ranks results by relevance.
    """

    def __init__(self, key_buffer: SecureBuffer, salt: bytes):
        """
        Initialize the search engine.

        Args:
            key_buffer: Encryption key for the search index
            salt: Salt used for key derivation
        """
        self.logger = logging.getLogger("SearchEngine")
        self._index = SearchIndex(key_buffer, salt)

    def open(self) -> None:
        """Open the search index."""
        self._index.open()

    def close(self, save: bool = True) -> None:
        """Close the search index."""
        self._index.close(save=save)

    def search(
        self,
        query: str,
        filter_type: SearchFilter = SearchFilter.ALL,
        notebook_id: str | None = None,
        limit: int = 50,
    ) -> list[SearchResult]:
        """
        Execute a search query.

        Args:
            query: User's search query
            filter_type: Type of elements to search
            notebook_id: Optional notebook ID filter
            limit: Maximum number of results

        Returns:
            List of SearchResult objects sorted by relevance
        """
        if not query or not query.strip():
            return []

        # Convert user query to FTS5 syntax
        fts_query = self._convert_to_fts5_query(query)
        if not fts_query:
            return []

        # Determine element types to search
        element_types: list[str] | None = None
        if filter_type == SearchFilter.TEXT_ONLY:
            element_types = ["text"]
        elif filter_type == SearchFilter.HANDWRITING_ONLY:
            element_types = ["stroke"]
        elif filter_type == SearchFilter.VOICE_ONLY:
            element_types = ["voice_memo"]

        # Execute search
        try:
            entries = self._index.search(
                fts_query,
                element_types=element_types,
                notebook_id=notebook_id,
                limit=limit,
            )
        except Exception as e:
            self.logger.warning("Search failed: %s", e)
            return []

        # Convert to SearchResult objects
        results: list[SearchResult] = []
        for i, entry in enumerate(entries):
            result = SearchResult.from_entry(entry)
            # Simple relevance scoring based on position
            result.relevance_score = 1.0 - (i / max(len(entries), 1))

            # Highlight matching text in snippet
            result.snippet = self._highlight_matches(result.snippet, query)

            results.append(result)

        return results

    def _convert_to_fts5_query(self, query: str) -> str:
        """
        Convert a user query to FTS5 syntax.

        Handles:
        - Quoted phrases: "exact match"
        - Boolean operators: AND, OR, NOT
        - Simple terms: word1 word2 (implicit AND)

        Args:
            query: User's search query

        Returns:
            FTS5-compatible query string
        """
        query = query.strip()
        if not query:
            return ""

        # Check for quoted phrases
        quoted_pattern = r'"([^"]+)"'
        quoted_matches = re.findall(quoted_pattern, query)

        # Remove quoted sections for processing rest
        remaining = re.sub(quoted_pattern, "", query).strip()

        # Process remaining terms
        terms: list[str] = []

        # Add quoted phrases back
        for phrase in quoted_matches:
            # FTS5 uses quotes for phrases
            terms.append(f'"{phrase}"')

        # Process individual words
        if remaining:
            words = remaining.split()
            for word in words:
                word = word.strip()
                if not word:
                    continue

                # Handle boolean operators (pass through)
                if word.upper() in ("AND", "OR", "NOT"):
                    terms.append(word.upper())
                else:
                    # Clean up the word and add wildcard for partial matching
                    clean_word = re.sub(r"[^\w\s]", "", word)
                    if clean_word:
                        if len(clean_word) >= settings.SEARCH_PREFIX_MIN_LENGTH:
                            # Add prefix matching for partial words
                            terms.append(f"{clean_word}*")
                        else:
                            terms.append(clean_word)

        if not terms:
            return ""

        # Join terms (FTS5 uses implicit AND)
        return " ".join(terms)

    def _highlight_matches(self, text: str, query: str) -> str:
        """
        Add highlighting markers around matching terms.

        Uses ** for bold in the UI (markdown-style).

        Args:
            text: Text to highlight
            query: Original search query

        Returns:
            Text with highlighting markers
        """
        # Extract search terms (ignore operators)
        terms = []
        for term in query.split():
            term = term.strip('"').strip()
            if term and term.upper() not in ("AND", "OR", "NOT"):
                # Remove special characters
                clean_term = re.sub(r"[^\w\s]", "", term)
                if clean_term:
                    terms.append(clean_term)

        if not terms:
            return text

        # Build pattern for all terms (case-insensitive)
        pattern = "|".join(re.escape(term) for term in terms)
        try:
            highlighted = re.sub(
                f"({pattern})",
                r"**\1**",
                text,
                flags=re.IGNORECASE,
            )
            return highlighted
        except re.error:
            return text

    def get_suggestions(self, partial_query: str, limit: int = 5) -> list[str]:
        """
        Get search suggestions based on partial input.

        Args:
            partial_query: Partial search query
            limit: Maximum number of suggestions

        Returns:
            List of suggested completions
        """
        # For now, return empty list - could be enhanced with
        # query history or common terms from the index
        return []

    def get_stats(self) -> dict[str, int]:
        """Get search index statistics."""
        return self._index.get_stats()
