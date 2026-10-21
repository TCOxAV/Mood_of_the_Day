"""Tests for the quotation validator and library loader."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from mood.quotes.validator import (
    ValidationError,
    validate_cache_entry,
    validate_quote,
    validate_quote_library,
)
from mood.quotes.library import QuoteLibrary, Quote
from mood.quotes.selector import QuoteSelector
from mood.learning.profile import UserProfile
from mood.storage.cache import DailyCache
from mood.providers.base import BaseProvider, QuoteSelection, ProviderError

class TestValidateQuote:
    """Tests for single-quote validation."""

    def _valid_quote(self, **overrides) -> dict:
        base = {
            "id": "test-001",
            "text": "Test quote text.",
            "author": "Test Author",
            "source": "Test Source (2024)",
            "themes": ["wisdom"],
            "verified": True,
        }
        base.update(overrides)
        return base

    def test_valid_quote_passes(self):
        result = validate_quote(self._valid_quote())
        assert result["id"] == "test-001"

    def test_missing_field_raises(self):
        q = self._valid_quote()
        del q["author"]
        with pytest.raises(ValidationError, match="Missing required field"):
            validate_quote(q)

    def test_wrong_type_raises(self):
        q = self._valid_quote(verified="yes")
        with pytest.raises(ValidationError, match="expected bool"):
            validate_quote(q)

    def test_empty_text_raises(self):
        q = self._valid_quote(text="   ")
        with pytest.raises(ValidationError, match="empty"):
            validate_quote(q)

    def test_empty_author_raises(self):
        q = self._valid_quote(author="")
        with pytest.raises(ValidationError, match="Author is empty"):
            validate_quote(q)

    def test_text_too_long_raises(self):
        q = self._valid_quote(text="x" * 2500)
        with pytest.raises(ValidationError, match="too long"):
            validate_quote(q)

    def test_too_many_themes_raises(self):
        q = self._valid_quote(themes=[f"theme-{i}" for i in range(25)])
        with pytest.raises(ValidationError, match="Too many themes"):
            validate_quote(q)

    def test_non_dict_raises(self):
        with pytest.raises(ValidationError, match="Expected dict"):
            validate_quote("not a dict")

class TestValidateCacheEntry:
    """Tests for cache entry validation."""

    def _valid_entry(self, **overrides) -> dict:
        base = {
            "quote_id": "test-001",
            "text": "Test quote.",
            "author": "Author",
            "source": "Source",
            "commentary": "This is a great quote.",
            "date": "2026-10-21",
            "themes": ["wisdom"],
            "verified": True,
        }
        base.update(overrides)
        return base

    def test_valid_entry_passes(self):
        result = validate_cache_entry(self._valid_entry())
        assert result["quote_id"] == "test-001"

    def test_bad_date_format_raises(self):
        with pytest.raises(ValidationError, match="Invalid date"):
            validate_cache_entry(self._valid_entry(date="10-21-2026"))

    def test_missing_commentary_raises(self):
        entry = self._valid_entry()
        del entry["commentary"]
        with pytest.raises(ValidationError, match="Missing required field"):
            validate_cache_entry(entry)

    def test_commentary_too_long_raises(self):
        entry = self._valid_entry(commentary="x" * 2000)
        with pytest.raises(ValidationError, match="Commentary too long"):
            validate_cache_entry(entry)

class TestValidateLibrary:
    """Tests for full library validation."""

    def test_valid_library(self):
        lib = {
            "version": 1,
            "quotes": [
                {
                    "id": "q1",
                    "text": "Quote one.",
                    "author": "Author",
                    "source": "Source",
                    "themes": ["test"],
                    "verified": True,
                }
            ],
        }
        result = validate_quote_library(lib)
        assert len(result["quotes"]) == 1

    def test_duplicate_ids_raise(self):
        lib = {
            "version": 1,
            "quotes": [
                {"id": "dup", "text": "A", "author": "X", "source": "S", "themes": [], "verified": True},
                {"id": "dup", "text": "B", "author": "Y", "source": "S", "themes": [], "verified": True},
            ],
        }
        with pytest.raises(ValidationError, match="Duplicate"):
            validate_quote_library(lib)

    def test_missing_quotes_key_raises(self):
        with pytest.raises(ValidationError, match="must have"):
            validate_quote_library({"version": 1})

class TestQuoteLibrary:
    """Tests for the QuoteLibrary class."""

    def _create_library_file(self, tmp_path: Path) -> Path:
        lib = {
            "version": 1,
            "quotes": [
                {
                    "id": "lib-001",
                    "text": "First quote.",
                    "author": "Author A",
                    "source": "Source A",
                    "themes": ["wisdom", "courage"],
                    "verified": True,
                    "notes": "",
                },
                {
                    "id": "lib-002",
                    "text": "Second quote.",
                    "author": "Author B",
                    "source": "Source B",
                    "themes": ["science"],
                    "verified": False,
                    "notes": "Unverified.",
                },
                {
                    "id": "lib-003",
                    "text": "Third quote.",
                    "author": "Author A",
                    "source": "Source C",
                    "themes": ["courage", "resilience"],
                    "verified": True,
                    "notes": "",
                },
            ],
        }
        file_path = tmp_path / "quotes.json"
        file_path.write_text(json.dumps(lib))
        return file_path

    def test_load_and_count(self, tmp_path):
        lib = QuoteLibrary()
        lib.load(str(self._create_library_file(tmp_path)))
        assert len(lib) == 3

    def test_get_by_id(self, tmp_path):
        lib = QuoteLibrary()
        lib.load(str(self._create_library_file(tmp_path)))
        quote = lib.get("lib-002")
        assert quote is not None
        assert quote.author == "Author B"

    def test_get_unknown_id_returns_none(self, tmp_path):
        lib = QuoteLibrary()
        lib.load(str(self._create_library_file(tmp_path)))
        assert lib.get("nonexistent") is None

    def test_filter_by_theme(self, tmp_path):
        lib = QuoteLibrary()
        lib.load(str(self._create_library_file(tmp_path)))
        results = lib.filter(themes=["courage"])
        assert len(results) == 2
        assert all("courage" in q.themes for q in results)

    def test_filter_verified_only(self, tmp_path):
        lib = QuoteLibrary()
        lib.load(str(self._create_library_file(tmp_path)))
        results = lib.filter(verified_only=True)
        assert len(results) == 2
        assert all(q.verified for q in results)

    def test_filter_exclude_ids(self, tmp_path):
        lib = QuoteLibrary()
        lib.load(str(self._create_library_file(tmp_path)))
        results = lib.filter(exclude_ids={"lib-001", "lib-003"})
        assert len(results) == 1
        assert results[0].id == "lib-002"

    def test_random_fallback(self, tmp_path):
        lib = QuoteLibrary()
        lib.load(str(self._create_library_file(tmp_path)))
        quote = lib.random_fallback()
        assert quote is not None
        assert quote.verified

    def test_random_fallback_with_all_excluded(self, tmp_path):
        lib = QuoteLibrary()
        lib.load(str(self._create_library_file(tmp_path)))
        quote = lib.random_fallback(exclude_ids={"lib-001", "lib-003"})
        assert quote is not None

    def test_load_bundled_library(self):
        """Verify the bundled data/quotes.json loads without errors."""
        lib = QuoteLibrary()
        lib.load()
        assert len(lib) >= 20

    def test_quote_immutability(self, tmp_path):
        lib = QuoteLibrary()
        lib.load(str(self._create_library_file(tmp_path)))
        quote = lib.get("lib-001")
        with pytest.raises(AttributeError):
            quote.text = "Modified!"  # type: ignore

class TestQuoteSelector:
    """Tests for QuoteSelector orchestrator."""

    def _make_library(self) -> QuoteLibrary:
        lib = QuoteLibrary()
        lib.load()
        return lib

    def test_get_today_returns_cached_entry(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mood.storage.cache.CACHE_PATH", tmp_path / "cache.json")
        monkeypatch.setattr("mood.storage.cache.DATA_DIR", tmp_path)
        monkeypatch.setattr("mood.storage.cache.ensure_dirs", lambda: None)
        monkeypatch.setattr("mood.learning.profile.PROFILE_PATH", tmp_path / "profile.json")
        monkeypatch.setattr("mood.learning.profile.PROFILE_BACKUP_PATH", tmp_path / "backup.json")
        monkeypatch.setattr("mood.learning.profile.DATA_DIR", tmp_path)
        monkeypatch.setattr("mood.learning.profile.ensure_dirs", lambda: None)

        cache = DailyCache()
        today = date.today().isoformat()
        cached_entry = {
            "quote_id": "q-cached",
            "text": "Cached quote.",
            "author": "Cached Author",
            "source": "Cached Source",
            "commentary": "Cached commentary.",
            "date": today,
            "themes": ["wisdom"],
            "verified": True,
            "is_fallback": False,
        }
        cache.set_entry(today, cached_entry)
        profile = UserProfile()
        profile.load()

        selector = QuoteSelector(library=self._make_library(), cache=cache, profile=profile)
        result = asyncio.run(selector.get_today())
        assert result["quote_id"] == "q-cached"
        assert result["text"] == "Cached quote."

    def test_get_today_fallback_when_no_provider(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mood.storage.cache.CACHE_PATH", tmp_path / "cache.json")
        monkeypatch.setattr("mood.storage.cache.DATA_DIR", tmp_path)
        monkeypatch.setattr("mood.storage.cache.ensure_dirs", lambda: None)
        monkeypatch.setattr("mood.learning.profile.PROFILE_PATH", tmp_path / "profile.json")
        monkeypatch.setattr("mood.learning.profile.PROFILE_BACKUP_PATH", tmp_path / "backup.json")
        monkeypatch.setattr("mood.learning.profile.DATA_DIR", tmp_path)
        monkeypatch.setattr("mood.learning.profile.ensure_dirs", lambda: None)

        cache = DailyCache()
        profile = UserProfile()
        profile.load()

        selector = QuoteSelector(
            library=self._make_library(),
            cache=cache,
            profile=profile,
            selection_provider=None,
        )
        result = asyncio.run(selector.get_today())
        assert result is not None
        assert result["is_fallback"] is True
        assert cache.get_today() is not None
        assert cache.get_today()["quote_id"] == result["quote_id"]

    def test_get_today_with_ai_provider(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mood.storage.cache.CACHE_PATH", tmp_path / "cache.json")
        monkeypatch.setattr("mood.storage.cache.DATA_DIR", tmp_path)
        monkeypatch.setattr("mood.storage.cache.ensure_dirs", lambda: None)
        monkeypatch.setattr("mood.learning.profile.PROFILE_PATH", tmp_path / "profile.json")
        monkeypatch.setattr("mood.learning.profile.PROFILE_BACKUP_PATH", tmp_path / "backup.json")
        monkeypatch.setattr("mood.learning.profile.DATA_DIR", tmp_path)
        monkeypatch.setattr("mood.learning.profile.ensure_dirs", lambda: None)

        cache = DailyCache()
        profile = UserProfile()
        profile.load()

        lib = self._make_library()
        valid_id = lib.all_quotes()[0].id

        mock_provider = MagicMock()
        mock_provider.is_configured.return_value = True
        mock_provider.select_quote = AsyncMock(
            return_value=QuoteSelection(quote_id=valid_id, commentary="Resonates deeply with your curiosity.")
        )

        selector = QuoteSelector(
            library=lib,
            cache=cache,
            profile=profile,
            selection_provider=mock_provider,
        )
        result = asyncio.run(selector.get_today())
        assert result["quote_id"] == valid_id
        assert result["is_fallback"] is False
        assert "curiosity" in result["commentary"].lower()
        assert valid_id in profile.recent_quote_ids
        assert cache.get_today()["quote_id"] == valid_id

    def test_get_today_ai_failure_uses_fallback(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mood.storage.cache.CACHE_PATH", tmp_path / "cache.json")
        monkeypatch.setattr("mood.storage.cache.DATA_DIR", tmp_path)
        monkeypatch.setattr("mood.storage.cache.ensure_dirs", lambda: None)
        monkeypatch.setattr("mood.learning.profile.PROFILE_PATH", tmp_path / "profile.json")
        monkeypatch.setattr("mood.learning.profile.PROFILE_BACKUP_PATH", tmp_path / "backup.json")
        monkeypatch.setattr("mood.learning.profile.DATA_DIR", tmp_path)
        monkeypatch.setattr("mood.learning.profile.ensure_dirs", lambda: None)

        cache = DailyCache()
        profile = UserProfile()
        profile.load()

        mock_provider = MagicMock()
        mock_provider.is_configured.return_value = True
        mock_provider.select_quote = AsyncMock(side_effect=ProviderError("Rate limit exceeded"))

        selector = QuoteSelector(
            library=self._make_library(),
            cache=cache,
            profile=profile,
            selection_provider=mock_provider,
        )
        result = asyncio.run(selector.get_today())
        assert result is not None
        assert result["is_fallback"] is True

    def test_fill_cache_populates_missing_dates(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mood.storage.cache.CACHE_PATH", tmp_path / "cache.json")
        monkeypatch.setattr("mood.storage.cache.DATA_DIR", tmp_path)
        monkeypatch.setattr("mood.storage.cache.ensure_dirs", lambda: None)
        monkeypatch.setattr("mood.learning.profile.PROFILE_PATH", tmp_path / "profile.json")
        monkeypatch.setattr("mood.learning.profile.PROFILE_BACKUP_PATH", tmp_path / "backup.json")
        monkeypatch.setattr("mood.learning.profile.DATA_DIR", tmp_path)
        monkeypatch.setattr("mood.learning.profile.ensure_dirs", lambda: None)

        cache = DailyCache()
        profile = UserProfile()
        profile.load()

        lib = self._make_library()
        call_ids = [q.id for q in lib.all_quotes()[:5]]
        idx = 0
        def fake_select(*args, **kwargs):
            nonlocal idx
            quote_id = call_ids[idx % len(call_ids)]
            idx += 1
            return QuoteSelection(quote_id=quote_id, commentary=f"Commentary for {quote_id}")

        mock_provider = MagicMock()
        mock_provider.is_configured.return_value = True
        mock_provider.select_quote = AsyncMock(side_effect=fake_select)

        selector = QuoteSelector(
            library=lib,
            cache=cache,
            profile=profile,
            selection_provider=mock_provider,
        )
        filled = asyncio.run(selector.fill_cache())
        assert filled == 5
        assert len(cache.missing_dates()) == 0

    def test_regenerate_today_updates_entry(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mood.storage.cache.CACHE_PATH", tmp_path / "cache.json")
        monkeypatch.setattr("mood.storage.cache.DATA_DIR", tmp_path)
        monkeypatch.setattr("mood.storage.cache.ensure_dirs", lambda: None)
        monkeypatch.setattr("mood.learning.profile.PROFILE_PATH", tmp_path / "profile.json")
        monkeypatch.setattr("mood.learning.profile.PROFILE_BACKUP_PATH", tmp_path / "backup.json")
        monkeypatch.setattr("mood.learning.profile.DATA_DIR", tmp_path)
        monkeypatch.setattr("mood.learning.profile.ensure_dirs", lambda: None)

        cache = DailyCache()
        profile = UserProfile()
        profile.load()

        lib = self._make_library()
        valid_id = lib.all_quotes()[1].id

        mock_provider = MagicMock()
        mock_provider.is_configured.return_value = True
        mock_provider.select_quote = AsyncMock(
            return_value=QuoteSelection(quote_id=valid_id, commentary="Fresh selection.")
        )

        selector = QuoteSelector(
            library=lib,
            cache=cache,
            profile=profile,
            selection_provider=mock_provider,
        )
        result = asyncio.run(selector.regenerate_today())
        assert result["quote_id"] == valid_id
        assert result["commentary"] == "Fresh selection."
        assert cache.get_today()["quote_id"] == valid_id
