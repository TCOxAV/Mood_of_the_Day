"""Five-day rolling cache for pre-generated daily quotations.

Design:
- Stores entries keyed by ISO date (YYYY-MM-DD).
- On every launch, prunes entries older than today.
- Keeps today + 4 future days (5 total).
- All writes are atomic (write-to-temp then os.replace).
- A file lock prevents concurrent launches from corrupting data.

The cache file lives at ~/.local/share/mood-of-the-day/cache.json
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import tempfile
from contextlib import contextmanager
from datetime import date, timedelta
from typing import Any, Optional

from mood.quotes.validator import ValidationError, validate_cache_entry
from mood.storage.paths import CACHE_PATH, DATA_DIR, ensure_dirs

logger = logging.getLogger(__name__)

CACHE_WINDOW = 5

@contextmanager
def _file_lock():
    """Acquire an exclusive lock to prevent concurrent cache writes.

    Uses fcntl.flock on a dedicated lock file. The lock is released
    when the context manager exits.
    """
    ensure_dirs()
    lock_path = DATA_DIR / "cache.lock"
    lock_fd = open(lock_path, "w")  # noqa: SIM115
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()

class DailyCache:
    """Manages the five-day rolling quotation cache."""

    def __init__(self) -> None:
        self._entries: dict[str, dict[str, Any]] = {}

    def load(self) -> None:
        """Load the cache from disk. Prunes stale entries."""
        if not CACHE_PATH.exists():
            self._entries = {}
            return

        try:
            with open(CACHE_PATH, encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Cache file unreadable, starting fresh: %s", exc)
            self._entries = {}
            return

        if not isinstance(raw, dict) or "entries" not in raw:
            logger.warning("Cache structure invalid, starting fresh.")
            self._entries = {}
            return

        today = date.today().isoformat()
        valid: dict[str, dict] = {}
        for date_key, entry in raw["entries"].items():
            if date_key < today:
                continue
            try:
                validate_cache_entry(entry)
                valid[date_key] = entry
            except ValidationError as exc:
                logger.warning("Discarding invalid cache entry for %s: %s", date_key, exc)

        self._entries = valid

    def save(self) -> None:
        """Persist the cache atomically with file locking."""
        ensure_dirs()
        with _file_lock():
            payload = json.dumps(
                {"version": 1, "entries": self._entries},
                indent=2,
                ensure_ascii=False,
            )
            fd, tmp_path = tempfile.mkstemp(
                dir=str(DATA_DIR), suffix=".tmp", prefix="cache_"
            )
            try:
                with open(fd, "w", encoding="utf-8") as f:
                    f.write(payload)
                os.replace(tmp_path, str(CACHE_PATH))
            except Exception:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise

    def get_today(self) -> Optional[dict]:
        """Return today's cache entry, or None."""
        return self._entries.get(date.today().isoformat())

    def get_entry(self, iso_date: str) -> Optional[dict]:
        """Return a cache entry for a specific date."""
        return self._entries.get(iso_date)

    def set_entry(self, iso_date: str, entry: dict) -> None:
        """Add or replace a cache entry after validation.

        Raises ``ValidationError`` if the entry is malformed.
        """
        validate_cache_entry(entry)
        self._entries[iso_date] = entry

    def missing_dates(self) -> list[str]:
        """Return ISO date strings for the cache window that lack entries."""
        today = date.today()
        needed: list[str] = []
        for offset in range(CACHE_WINDOW):
            d = (today + timedelta(days=offset)).isoformat()
            if d not in self._entries:
                needed.append(d)
        return needed

    def cached_quote_ids(self) -> set[str]:
        """Return IDs of all quotes currently in the cache.

        Used to avoid duplicates when generating new entries.
        """
        return {
            entry["quote_id"]
            for entry in self._entries.values()
            if "quote_id" in entry
        }

    def prune(self) -> None:
        """Remove entries for dates before today."""
        today = date.today().isoformat()
        stale = [k for k in self._entries if k < today]
        for k in stale:
            del self._entries[k]

    def clear(self) -> None:
        """Remove all entries."""
        self._entries.clear()
