"""User profile — schema, I/O, and validation.

The profile is a human-readable JSON file that stores:
- User-provided info (name, interests, tone preferences)
- Learned preferences (built up from feedback over time)
- Feedback history (compact; old entries are summarized)
- Recently displayed quote IDs

The profile is stored at ~/.local/share/mood-of-the-day/profile.json
and never contains API keys or raw AI responses.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import shutil
import tempfile
from datetime import datetime
from typing import Any, Optional

from mood.storage.paths import (
    DATA_DIR,
    PROFILE_BACKUP_PATH,
    PROFILE_PATH,
    ensure_dirs,
)

logger = logging.getLogger(__name__)

MAX_FEEDBACK_HISTORY = 50
MAX_RECENT_QUOTES = 30

_DEFAULT_PROFILE: dict[str, Any] = {
    "version": 1,
    "user": {
        "name": "",
        "personality": "",
        "preferred_tone": "",
        "preferred_themes": [],
    },
    "learned": {
        "liked_themes": [],
        "disliked_themes": [],
        "liked_authors": [],
        "disliked_authors": [],
        "notes": "",
    },
    "feedback_history": [],
    "recent_quote_ids": [],
    "created_at": "",
    "updated_at": "",
}

def _validate_profile(data: Any) -> dict:
    """Ensure the profile has the expected structure.

    Missing top-level keys are filled from defaults.
    Raises ``ValueError`` for fundamentally broken data.
    """
    if not isinstance(data, dict):
        raise ValueError(f"Profile root must be a dict, got {type(data).__name__}")

    for key, default in _DEFAULT_PROFILE.items():
        if key not in data:
            data[key] = copy.deepcopy(default)

    if not isinstance(data.get("user"), dict):
        data["user"] = copy.deepcopy(_DEFAULT_PROFILE["user"])
    if not isinstance(data.get("learned"), dict):
        data["learned"] = copy.deepcopy(_DEFAULT_PROFILE["learned"])
    if not isinstance(data.get("feedback_history"), list):
        data["feedback_history"] = []
    if not isinstance(data.get("recent_quote_ids"), list):
        data["recent_quote_ids"] = []

    return data

class UserProfile:
    """Read/write interface for the user's learning profile."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._loaded = False

    @property
    def data(self) -> dict[str, Any]:
        if not self._loaded:
            self.load()
        return self._data

    @property
    def exists(self) -> bool:
        """True if a profile has been saved to disk."""
        return PROFILE_PATH.exists()

    def load(self) -> None:
        """Load from disk, creating defaults if missing."""
        if not PROFILE_PATH.exists():
            self._data = _validate_profile(copy.deepcopy(_DEFAULT_PROFILE))
            self._data["created_at"] = datetime.now().isoformat()
            self._loaded = True
            return

        try:
            with open(PROFILE_PATH, encoding="utf-8") as f:
                raw = json.load(f)
            self._data = _validate_profile(raw)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            logger.error("Profile load failed, using defaults: %s", exc)
            self._data = _validate_profile(copy.deepcopy(_DEFAULT_PROFILE))

        self._loaded = True

    def save(self) -> None:
        """Persist the profile atomically. Creates a backup first."""
        ensure_dirs()
        self._data["updated_at"] = datetime.now().isoformat()

        if PROFILE_PATH.exists():
            try:
                shutil.copy2(str(PROFILE_PATH), str(PROFILE_BACKUP_PATH))
            except OSError as exc:
                logger.warning("Profile backup failed: %s", exc)

        payload = json.dumps(self._data, indent=2, ensure_ascii=False)
        fd, tmp_path = tempfile.mkstemp(dir=str(DATA_DIR), suffix=".tmp")
        try:
            with open(fd, "w", encoding="utf-8") as f:
                f.write(payload)
            os.replace(tmp_path, str(PROFILE_PATH))
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    @property
    def name(self) -> str:
        return self.data.get("user", {}).get("name", "")

    @name.setter
    def name(self, value: str) -> None:
        self.data.setdefault("user", {})["name"] = value

    @property
    def personality(self) -> str:
        return self.data.get("user", {}).get("personality", "")

    @personality.setter
    def personality(self, value: str) -> None:
        self.data.setdefault("user", {})["personality"] = value

    @property
    def preferred_tone(self) -> str:
        return self.data.get("user", {}).get("preferred_tone", "")

    @preferred_tone.setter
    def preferred_tone(self, value: str) -> None:
        self.data.setdefault("user", {})["preferred_tone"] = value

    @property
    def preferred_themes(self) -> list[str]:
        return self.data.get("user", {}).get("preferred_themes", [])

    @preferred_themes.setter
    def preferred_themes(self, value: list[str]) -> None:
        self.data.setdefault("user", {})["preferred_themes"] = value

    @property
    def learned(self) -> dict:
        return self.data.get("learned", {})

    @property
    def recent_quote_ids(self) -> list[str]:
        return self.data.get("recent_quote_ids", [])

    def add_recent_quote(self, quote_id: str) -> None:
        """Track a recently displayed quote ID."""
        recents = self.data.setdefault("recent_quote_ids", [])
        if quote_id not in recents:
            recents.append(quote_id)
        while len(recents) > MAX_RECENT_QUOTES:
            recents.pop(0)

    def add_feedback(self, quote_id: str, liked: bool, comment: str = "") -> None:
        """Record a feedback entry."""
        history = self.data.setdefault("feedback_history", [])
        history.append({
            "quote_id": quote_id,
            "liked": liked,
            "comment": comment,
            "timestamp": datetime.now().isoformat(),
        })
        while len(history) > MAX_FEEDBACK_HISTORY:
            history.pop(0)

    def get_feedback_summary(self) -> dict:
        """Return a compact summary of feedback suitable for sending to an API.

        Never sends the full history — only aggregate counts and recent signals.
        """
        history = self.data.get("feedback_history", [])
        liked_themes: dict[str, int] = {}
        disliked_themes: dict[str, int] = {}
        total_likes = sum(1 for f in history if f.get("liked"))
        total_dislikes = len(history) - total_likes

        return {
            "total_likes": total_likes,
            "total_dislikes": total_dislikes,
            "recent_feedback_count": min(len(history), 10),
            "learned_preferences": self.learned,
        }

    def reset_learned(self) -> None:
        """Clear learned preferences (keeps user-provided info)."""
        self._data["learned"] = copy.deepcopy(_DEFAULT_PROFILE["learned"])
        self._data["feedback_history"] = []
        self._data["recent_quote_ids"] = []

    def get_preference_summary(self) -> str:
        """Return a compact text summary of user preferences for AI prompts.

        Minimizes personal information while giving enough context
        for meaningful quote selection.
        """
        parts: list[str] = []
        if self.name:
            parts.append(f"Name: {self.name}")
        if self.personality:
            parts.append(f"Interests/personality: {self.personality}")
        if self.preferred_tone:
            parts.append(f"Preferred tone: {self.preferred_tone}")
        if self.preferred_themes:
            parts.append(f"Preferred themes: {', '.join(self.preferred_themes)}")

        learned = self.learned
        if learned.get("liked_themes"):
            parts.append(f"Liked themes: {', '.join(learned['liked_themes'])}")
        if learned.get("disliked_themes"):
            parts.append(f"Disliked themes: {', '.join(learned['disliked_themes'])}")
        if learned.get("liked_authors"):
            parts.append(f"Liked authors: {', '.join(learned['liked_authors'])}")

        return "\n".join(parts) if parts else "No preferences set yet."
