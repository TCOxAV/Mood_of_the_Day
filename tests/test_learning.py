"""Tests for the learning profile and feedback system."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mood.learning.profile import UserProfile, _validate_profile, MAX_FEEDBACK_HISTORY
from mood.learning.feedback import FeedbackProcessor
from mood.learning.manager import LearningManager
from mood.providers.base import ProfileUpdate, ProviderError
from unittest.mock import AsyncMock, MagicMock
import asyncio

class TestProfileValidation:
    """Tests for profile schema validation."""

    def test_valid_profile(self):
        data = {
            "version": 1,
            "user": {"name": "Test", "personality": "", "preferred_tone": "", "preferred_themes": []},
            "learned": {"liked_themes": [], "disliked_themes": [], "liked_authors": [], "disliked_authors": [], "notes": ""},
            "feedback_history": [],
            "recent_quote_ids": [],
            "created_at": "",
            "updated_at": "",
        }
        result = _validate_profile(data)
        assert result["user"]["name"] == "Test"

    def test_missing_keys_filled_from_defaults(self):
        result = _validate_profile({"version": 1})
        assert "user" in result
        assert "learned" in result
        assert isinstance(result["feedback_history"], list)

    def test_non_dict_raises(self):
        with pytest.raises(ValueError, match="must be a dict"):
            _validate_profile("not a dict")

    def test_corrupt_sub_structures_reset(self):
        data = {"version": 1, "user": "not a dict", "learned": 42}
        result = _validate_profile(data)
        assert isinstance(result["user"], dict)
        assert isinstance(result["learned"], dict)

class TestUserProfile:
    """Tests for UserProfile I/O and accessors."""

    def test_new_profile_defaults(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mood.learning.profile.PROFILE_PATH", tmp_path / "profile.json")
        monkeypatch.setattr("mood.learning.profile.PROFILE_BACKUP_PATH", tmp_path / "backup.json")
        monkeypatch.setattr("mood.learning.profile.DATA_DIR", tmp_path)
        monkeypatch.setattr("mood.learning.profile.ensure_dirs", lambda: None)

        profile = UserProfile()
        profile.load()
        assert profile.name == ""
        assert profile.personality == ""

    def test_save_and_reload(self, tmp_path, monkeypatch):
        profile_path = tmp_path / "profile.json"
        monkeypatch.setattr("mood.learning.profile.PROFILE_PATH", profile_path)
        monkeypatch.setattr("mood.learning.profile.PROFILE_BACKUP_PATH", tmp_path / "backup.json")
        monkeypatch.setattr("mood.learning.profile.DATA_DIR", tmp_path)
        monkeypatch.setattr("mood.learning.profile.ensure_dirs", lambda: None)

        p1 = UserProfile()
        p1.load()
        p1.name = "TestUser"
        p1.personality = "Curious engineer"
        p1.preferred_themes = ["science", "philosophy"]
        p1.save()

        p2 = UserProfile()
        p2.load()
        assert p2.name == "TestUser"
        assert p2.personality == "Curious engineer"
        assert p2.preferred_themes == ["science", "philosophy"]

    def test_backup_created_on_save(self, tmp_path, monkeypatch):
        profile_path = tmp_path / "profile.json"
        backup_path = tmp_path / "backup.json"
        monkeypatch.setattr("mood.learning.profile.PROFILE_PATH", profile_path)
        monkeypatch.setattr("mood.learning.profile.PROFILE_BACKUP_PATH", backup_path)
        monkeypatch.setattr("mood.learning.profile.DATA_DIR", tmp_path)
        monkeypatch.setattr("mood.learning.profile.ensure_dirs", lambda: None)

        profile = UserProfile()
        profile.load()
        profile.name = "First"
        profile.save()

        profile.name = "Second"
        profile.save()

        assert backup_path.exists()
        backup_data = json.loads(backup_path.read_text())
        assert backup_data["user"]["name"] == "First"

    def test_add_feedback(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mood.learning.profile.PROFILE_PATH", tmp_path / "profile.json")
        monkeypatch.setattr("mood.learning.profile.PROFILE_BACKUP_PATH", tmp_path / "backup.json")
        monkeypatch.setattr("mood.learning.profile.DATA_DIR", tmp_path)
        monkeypatch.setattr("mood.learning.profile.ensure_dirs", lambda: None)

        profile = UserProfile()
        profile.load()
        profile.add_feedback("q-001", liked=True)
        profile.add_feedback("q-002", liked=False, comment="Too dark")

        history = profile.data["feedback_history"]
        assert len(history) == 2
        assert history[0]["liked"] is True
        assert history[1]["comment"] == "Too dark"

    def test_feedback_trimming(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mood.learning.profile.PROFILE_PATH", tmp_path / "profile.json")
        monkeypatch.setattr("mood.learning.profile.PROFILE_BACKUP_PATH", tmp_path / "backup.json")
        monkeypatch.setattr("mood.learning.profile.DATA_DIR", tmp_path)
        monkeypatch.setattr("mood.learning.profile.ensure_dirs", lambda: None)

        profile = UserProfile()
        profile.load()

        for i in range(MAX_FEEDBACK_HISTORY + 10):
            profile.add_feedback(f"q-{i:04d}", liked=(i % 2 == 0))

        history = profile.data["feedback_history"]
        assert len(history) == MAX_FEEDBACK_HISTORY

    def test_feedback_summary_is_compact(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mood.learning.profile.PROFILE_PATH", tmp_path / "profile.json")
        monkeypatch.setattr("mood.learning.profile.PROFILE_BACKUP_PATH", tmp_path / "backup.json")
        monkeypatch.setattr("mood.learning.profile.DATA_DIR", tmp_path)
        monkeypatch.setattr("mood.learning.profile.ensure_dirs", lambda: None)

        profile = UserProfile()
        profile.load()
        profile.add_feedback("q-1", liked=True)
        profile.add_feedback("q-2", liked=False)

        summary = profile.get_feedback_summary()
        assert summary["total_likes"] == 1
        assert summary["total_dislikes"] == 1
        assert "feedback_history" not in summary or isinstance(
            summary.get("feedback_history"), type(None)
        )

    def test_reset_learned_preserves_user_info(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mood.learning.profile.PROFILE_PATH", tmp_path / "profile.json")
        monkeypatch.setattr("mood.learning.profile.PROFILE_BACKUP_PATH", tmp_path / "backup.json")
        monkeypatch.setattr("mood.learning.profile.DATA_DIR", tmp_path)
        monkeypatch.setattr("mood.learning.profile.ensure_dirs", lambda: None)

        profile = UserProfile()
        profile.load()
        profile.name = "KeepMe"
        profile.data["learned"]["liked_themes"] = ["stoicism"]
        profile.add_feedback("q-1", liked=True)

        profile.reset_learned()

        assert profile.name == "KeepMe"
        assert profile.learned["liked_themes"] == []
        assert len(profile.data["feedback_history"]) == 0

    def test_recent_quote_tracking(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mood.learning.profile.PROFILE_PATH", tmp_path / "profile.json")
        monkeypatch.setattr("mood.learning.profile.PROFILE_BACKUP_PATH", tmp_path / "backup.json")
        monkeypatch.setattr("mood.learning.profile.DATA_DIR", tmp_path)
        monkeypatch.setattr("mood.learning.profile.ensure_dirs", lambda: None)

        profile = UserProfile()
        profile.load()
        profile.add_recent_quote("q-001")
        profile.add_recent_quote("q-002")
        profile.add_recent_quote("q-001")

        assert profile.recent_quote_ids == ["q-001", "q-002"]

class TestLearningManager:
    """Tests for the learning manager's validation."""

    def test_valid_update_applied(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mood.learning.profile.PROFILE_PATH", tmp_path / "profile.json")
        monkeypatch.setattr("mood.learning.profile.PROFILE_BACKUP_PATH", tmp_path / "backup.json")
        monkeypatch.setattr("mood.learning.profile.DATA_DIR", tmp_path)
        monkeypatch.setattr("mood.learning.profile.ensure_dirs", lambda: None)

        profile = UserProfile()
        profile.load()
        manager = LearningManager(profile=profile)

        update = ProfileUpdate(
            add_liked_themes=["courage", "science"],
            add_disliked_themes=["nihilism"],
            add_liked_authors=["Feynman"],
            add_disliked_authors=[],
            notes="Based on recent likes.",
        )

        result = manager._apply_update(update)
        assert result is not None
        assert "courage" in profile.learned["liked_themes"]
        assert "nihilism" in profile.learned["disliked_themes"]
        assert "Feynman" in profile.learned["liked_authors"]

    def test_oversized_update_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mood.learning.profile.PROFILE_PATH", tmp_path / "profile.json")
        monkeypatch.setattr("mood.learning.profile.PROFILE_BACKUP_PATH", tmp_path / "backup.json")
        monkeypatch.setattr("mood.learning.profile.DATA_DIR", tmp_path)
        monkeypatch.setattr("mood.learning.profile.ensure_dirs", lambda: None)

        profile = UserProfile()
        profile.load()
        manager = LearningManager(profile=profile)

        update = ProfileUpdate(
            add_liked_themes=[f"theme-{i}" for i in range(15)],
            add_disliked_themes=[],
            add_liked_authors=[],
            add_disliked_authors=[],
        )

        result = manager._apply_update(update)
        assert result is None

    def test_non_string_items_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mood.learning.profile.PROFILE_PATH", tmp_path / "profile.json")
        monkeypatch.setattr("mood.learning.profile.PROFILE_BACKUP_PATH", tmp_path / "backup.json")
        monkeypatch.setattr("mood.learning.profile.DATA_DIR", tmp_path)
        monkeypatch.setattr("mood.learning.profile.ensure_dirs", lambda: None)

        profile = UserProfile()
        profile.load()
        manager = LearningManager(profile=profile)

        update = ProfileUpdate(
            add_liked_themes=[123, None],  # type: ignore
            add_disliked_themes=[],
            add_liked_authors=[],
            add_disliked_authors=[],
        )

        result = manager._apply_update(update)
        assert result is None

    def test_duplicate_items_not_added(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mood.learning.profile.PROFILE_PATH", tmp_path / "profile.json")
        monkeypatch.setattr("mood.learning.profile.PROFILE_BACKUP_PATH", tmp_path / "backup.json")
        monkeypatch.setattr("mood.learning.profile.DATA_DIR", tmp_path)
        monkeypatch.setattr("mood.learning.profile.ensure_dirs", lambda: None)

        profile = UserProfile()
        profile.load()
        profile.data["learned"]["liked_themes"] = ["stoicism"]

        manager = LearningManager(profile=profile)
        update = ProfileUpdate(
            add_liked_themes=["stoicism"],
            add_disliked_themes=[],
            add_liked_authors=[],
            add_disliked_authors=[],
        )

        result = manager._apply_update(update)
        assert result is None
        assert profile.learned["liked_themes"].count("stoicism") == 1

    def test_run_learning_cycle_success(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mood.learning.profile.PROFILE_PATH", tmp_path / "profile.json")
        monkeypatch.setattr("mood.learning.profile.PROFILE_BACKUP_PATH", tmp_path / "backup.json")
        monkeypatch.setattr("mood.learning.profile.DATA_DIR", tmp_path)
        monkeypatch.setattr("mood.learning.profile.ensure_dirs", lambda: None)

        profile = UserProfile()
        profile.load()

        mock_provider = MagicMock()
        mock_provider.is_configured.return_value = True
        mock_provider.update_profile = AsyncMock(
            return_value=ProfileUpdate(
                add_liked_themes=["resilience"],
                add_disliked_themes=[],
                add_liked_authors=["Epictetus"],
                add_disliked_authors=[],
                notes="Learned from positive reactions",
            )
        )

        manager = LearningManager(profile=profile, learning_provider=mock_provider)
        summary = asyncio.run(manager.run_learning_cycle())

        assert summary is not None
        assert "resilience" in profile.learned["liked_themes"]
        assert "Epictetus" in profile.learned["liked_authors"]

    def test_run_learning_cycle_provider_failure(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mood.learning.profile.PROFILE_PATH", tmp_path / "profile.json")
        monkeypatch.setattr("mood.learning.profile.PROFILE_BACKUP_PATH", tmp_path / "backup.json")
        monkeypatch.setattr("mood.learning.profile.DATA_DIR", tmp_path)
        monkeypatch.setattr("mood.learning.profile.ensure_dirs", lambda: None)

        profile = UserProfile()
        profile.load()

        mock_provider = MagicMock()
        mock_provider.is_configured.return_value = True
        mock_provider.update_profile = AsyncMock(side_effect=ProviderError("Rate limit"))

        manager = LearningManager(profile=profile, learning_provider=mock_provider)
        summary = asyncio.run(manager.run_learning_cycle())
        assert summary is None

class TestFeedbackProcessor:
    """Tests for feedback processor logic."""

    def test_record_feedback_and_trigger_threshold(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mood.learning.profile.PROFILE_PATH", tmp_path / "profile.json")
        monkeypatch.setattr("mood.learning.profile.PROFILE_BACKUP_PATH", tmp_path / "backup.json")
        monkeypatch.setattr("mood.learning.profile.DATA_DIR", tmp_path)
        monkeypatch.setattr("mood.learning.profile.ensure_dirs", lambda: None)

        profile = UserProfile()
        profile.load()
        processor = FeedbackProcessor(profile)

        assert processor.should_trigger_learning() is False

        for i in range(1, 5):
            processor.record(f"q-{i}", liked=True)
            assert processor.should_trigger_learning() is False

        processor.record("q-5", liked=False)
        assert processor.should_trigger_learning() is True

        history = profile.data["feedback_history"]
        assert len(history) == 5
        assert history[-1]["quote_id"] == "q-5"
        assert history[-1]["liked"] is False
