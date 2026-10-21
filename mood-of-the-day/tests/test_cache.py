"""Tests for the five-day rolling cache."""

from __future__ import annotations

import json
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from mood.quotes.validator import ValidationError
from mood.storage.cache import DailyCache, CACHE_WINDOW
from mood.storage.config import (
    store_api_key,
    get_api_key,
    delete_api_key,
    has_any_provider,
    is_keyring_available,
)
from mood.system.autostart import (
    install_autostart,
    uninstall_autostart,
    is_autostart_installed,
    _desktop_entry_content,
)

def _make_entry(iso_date: str, quote_id: str = "q-001") -> dict:
    """Create a valid cache entry for testing."""
    return {
        "quote_id": quote_id,
        "text": "Test quote text.",
        "author": "Test Author",
        "source": "Test Source",
        "commentary": "Test commentary.",
        "date": iso_date,
        "themes": ["test"],
        "verified": True,
    }

class TestDailyCache:
    """Tests for DailyCache operations."""

    def test_empty_cache(self):
        cache = DailyCache()
        assert cache.get_today() is None

    def test_set_and_get_entry(self):
        cache = DailyCache()
        today = date.today().isoformat()
        entry = _make_entry(today)
        cache.set_entry(today, entry)
        assert cache.get_entry(today) is not None
        assert cache.get_entry(today)["quote_id"] == "q-001"

    def test_invalid_entry_rejected(self):
        cache = DailyCache()
        today = date.today().isoformat()
        with pytest.raises(ValidationError):
            cache.set_entry(today, {"bad": "data"})

    def test_missing_dates(self):
        cache = DailyCache()
        missing = cache.missing_dates()
        assert len(missing) == CACHE_WINDOW

    def test_missing_dates_with_partial_fill(self):
        cache = DailyCache()
        today = date.today().isoformat()
        cache.set_entry(today, _make_entry(today))
        missing = cache.missing_dates()
        assert len(missing) == CACHE_WINDOW - 1
        assert today not in missing

    def test_cached_quote_ids(self):
        cache = DailyCache()
        today = date.today()
        for i in range(3):
            d = (today + timedelta(days=i)).isoformat()
            cache.set_entry(d, _make_entry(d, f"q-{i:03d}"))

        ids = cache.cached_quote_ids()
        assert ids == {"q-000", "q-001", "q-002"}

    def test_no_duplicate_detection(self):
        cache = DailyCache()
        today = date.today()
        d1 = today.isoformat()
        d2 = (today + timedelta(days=1)).isoformat()

        cache.set_entry(d1, _make_entry(d1, "q-same"))
        cache.set_entry(d2, _make_entry(d2, "q-same"))

        assert cache.get_entry(d1)["quote_id"] == "q-same"
        assert cache.get_entry(d2)["quote_id"] == "q-same"

    def test_prune_removes_past_entries(self):
        cache = DailyCache()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        today = date.today().isoformat()

        cache.set_entry(yesterday, _make_entry(yesterday))
        cache.set_entry(today, _make_entry(today))

        cache.prune()

        assert cache.get_entry(yesterday) is None
        assert cache.get_entry(today) is not None

    def test_clear_removes_everything(self):
        cache = DailyCache()
        today = date.today().isoformat()
        cache.set_entry(today, _make_entry(today))
        cache.clear()
        assert cache.get_today() is None

    def test_save_and_load(self, tmp_path, monkeypatch):
        """Test atomic save/load cycle using a temp directory."""
        cache_path = tmp_path / "cache.json"
        data_dir = tmp_path

        monkeypatch.setattr("mood.storage.cache.CACHE_PATH", cache_path)
        monkeypatch.setattr("mood.storage.cache.DATA_DIR", data_dir)
        monkeypatch.setattr(
            "mood.storage.cache.ensure_dirs", lambda: None
        )

        cache1 = DailyCache()
        today = date.today().isoformat()
        cache1.set_entry(today, _make_entry(today, "saved-quote"))
        cache1.save()

        assert cache_path.exists()
        raw = json.loads(cache_path.read_text())
        assert "entries" in raw

        cache2 = DailyCache()
        cache2.load()
        assert cache2.get_today()["quote_id"] == "saved-quote"

class TestDateRollover:
    """Tests for date boundary handling."""

    def test_entries_span_correct_window(self):
        cache = DailyCache()
        today = date.today()
        missing = cache.missing_dates()

        expected = [
            (today + timedelta(days=i)).isoformat()
            for i in range(CACHE_WINDOW)
        ]
        assert missing == expected

    def test_past_entries_pruned_on_load(self, tmp_path, monkeypatch):
        """Simulate loading a cache with stale entries."""
        cache_path = tmp_path / "cache.json"
        monkeypatch.setattr("mood.storage.cache.CACHE_PATH", cache_path)

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        today = date.today().isoformat()

        data = {
            "version": 1,
            "entries": {
                yesterday: _make_entry(yesterday),
                today: _make_entry(today),
            },
        }
        cache_path.write_text(json.dumps(data))

        cache = DailyCache()
        cache.load()

        assert cache.get_entry(yesterday) is None
        assert cache.get_entry(today) is not None

class TestKeyStorage:
    """Tests for API key storage (fallback file and keyring)."""

    def test_fallback_file_store_and_retrieve(self, tmp_path, monkeypatch):
        key_file = tmp_path / "keys.json"
        monkeypatch.setattr("mood.storage.config.KEY_FALLBACK_PATH", key_file)
        monkeypatch.setattr("mood.storage.config._KEYRING_AVAILABLE", False)
        monkeypatch.setattr("mood.storage.config.ensure_dirs", lambda: None)

        assert get_api_key("openai") is None
        assert has_any_provider() is False

        store_api_key("openai", "sk-test-secret")
        assert get_api_key("openai") == "sk-test-secret"
        assert has_any_provider() is True

        mode = key_file.stat().st_mode & 0o777
        assert mode == 0o600

        delete_api_key("openai")
        assert get_api_key("openai") is None
        assert has_any_provider() is False

class TestAutostart:
    """Tests for XDG desktop autostart entry creation and removal."""

    def test_install_and_uninstall_autostart(self, tmp_path, monkeypatch):
        desktop_file = tmp_path / "autostart" / "mood-of-the-day.desktop"
        monkeypatch.setattr("mood.system.autostart._AUTOSTART_DIR", tmp_path / "autostart")
        monkeypatch.setattr("mood.system.autostart._DESKTOP_FILE_PATH", desktop_file)

        assert is_autostart_installed() is False

        success = install_autostart()
        assert success is True
        assert is_autostart_installed() is True
        assert desktop_file.exists()

        content = desktop_file.read_text(encoding="utf-8")
        assert "[Desktop Entry]" in content
        assert "Mood of the Day" in content
        assert "-m mood.main" in content

        removed = uninstall_autostart()
        assert removed is True
        assert is_autostart_installed() is False
        assert not desktop_file.exists()
