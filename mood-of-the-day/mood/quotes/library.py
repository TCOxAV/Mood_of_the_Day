"""Load and query the bundled quotation library.

The library is a read-only JSON file shipped with the application.
This module provides typed access and basic querying (by theme,
excluding recent IDs, etc.).
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass, field
from typing import Optional

from mood.quotes.validator import validate_quote_library, ValidationError
from mood.storage.paths import QUOTES_LIBRARY_PATH

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class Quote:
    """An immutable quotation record."""

    id: str
    text: str
    author: str
    source: str
    themes: tuple[str, ...]
    verified: bool
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "Quote":
        return cls(
            id=data["id"],
            text=data["text"],
            author=data["author"],
            source=data["source"],
            themes=tuple(data.get("themes", [])),
            verified=data.get("verified", False),
            notes=data.get("notes", ""),
        )

class QuoteLibrary:
    """In-memory index of the bundled quotation library."""

    def __init__(self) -> None:
        self._quotes: list[Quote] = []
        self._by_id: dict[str, Quote] = {}

    def load(self, path: Optional[str] = None) -> None:
        """Load quotes from the JSON library file.

        Raises ``RuntimeError`` if the file is missing or invalid.
        """
        lib_path = path or str(QUOTES_LIBRARY_PATH)
        try:
            with open(lib_path, encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Cannot load quote library: {exc}") from exc

        try:
            validate_quote_library(raw)
        except ValidationError as exc:
            raise RuntimeError(f"Quote library validation failed: {exc}") from exc

        self._quotes = [Quote.from_dict(q) for q in raw["quotes"]]
        self._by_id = {q.id: q for q in self._quotes}
        logger.info("Loaded %d quotes from library.", len(self._quotes))

    def get(self, quote_id: str) -> Optional[Quote]:
        """Look up a quote by its stable ID."""
        return self._by_id.get(quote_id)

    def all_quotes(self) -> list[Quote]:
        """Return all loaded quotes."""
        return list(self._quotes)

    def filter(
        self,
        themes: Optional[list[str]] = None,
        exclude_ids: Optional[set[str]] = None,
        verified_only: bool = False,
    ) -> list[Quote]:
        """Return quotes matching the given criteria.

        Args:
            themes: If given, only quotes whose themes overlap with
                this list are returned.
            exclude_ids: Quote IDs to exclude (e.g. recently shown).
            verified_only: If True, only return verified quotes.
        """
        results = self._quotes

        if verified_only:
            results = [q for q in results if q.verified]

        if exclude_ids:
            results = [q for q in results if q.id not in exclude_ids]

        if themes:
            theme_set = set(themes)
            results = [
                q for q in results
                if set(q.themes) & theme_set
            ]

        return results

    def random_fallback(self, exclude_ids: Optional[set[str]] = None) -> Optional[Quote]:
        """Pick a random verified quote, avoiding recently shown ones.

        Used when no AI provider is available and we need a fallback.
        """
        candidates = self.filter(verified_only=True, exclude_ids=exclude_ids)
        if not candidates:
            candidates = self.filter(verified_only=True)
        if not candidates:
            candidates = self._quotes
        return random.choice(candidates) if candidates else None

    def __len__(self) -> int:
        return len(self._quotes)
