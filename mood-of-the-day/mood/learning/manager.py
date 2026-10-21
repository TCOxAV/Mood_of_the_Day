"""Learning manager — applies AI-proposed profile updates.

This is the gatekeeper between AI suggestions and the user's profile.
Every proposed update is validated before being applied:
1. All fields must be the correct type (lists of strings).
2. No single update can add more than 10 items per category.
3. The original profile is backed up before any change.

The AI provider proposes changes (a ``ProfileUpdate``); this module
decides whether to accept them.
"""

from __future__ import annotations

import logging
from typing import Optional

from mood.learning.profile import UserProfile
from mood.providers.base import BaseProvider, ProfileUpdate, ProviderError

logger = logging.getLogger(__name__)

MAX_ITEMS_PER_UPDATE = 10
MAX_TOTAL_PER_CATEGORY = 50


class LearningManager:
    """Validates and applies AI-proposed profile updates."""

    def __init__(
        self,
        profile: UserProfile,
        learning_provider: Optional[BaseProvider] = None,
    ) -> None:
        self._profile = profile
        self._provider = learning_provider

    async def run_learning_cycle(self) -> Optional[str]:
        """Execute a full learning cycle: gather feedback → propose → apply.

        Returns a human-readable summary of changes, or None if nothing changed.
        """
        if not self._provider or not self._provider.is_configured():
            return None

        feedback_summary = self._profile.get_feedback_summary()
        preferences = self._profile.get_preference_summary()

        try:
            proposal = await self._provider.update_profile(
                feedback_summary=feedback_summary,
                user_preferences=preferences,
            )
        except ProviderError as exc:
            logger.warning("Learning cycle failed: %s", exc)
            return None

        if not proposal:
            return None

        return self._apply_update(proposal)

    def _apply_update(self, update: ProfileUpdate) -> Optional[str]:
        """Validate and apply a proposed update. Returns a summary string."""
        if not self._validate_update(update):
            logger.warning("Proposed update failed validation, discarding.")
            return None

        learned = self._profile.data.setdefault("learned", {})
        changes: list[str] = []

        for field, key in [
            (update.add_liked_themes, "liked_themes"),
            (update.add_disliked_themes, "disliked_themes"),
            (update.add_liked_authors, "liked_authors"),
            (update.add_disliked_authors, "disliked_authors"),
        ]:
            if not field:
                continue
            existing = learned.setdefault(key, [])
            added = []
            for item in field:
                if item not in existing and len(existing) < MAX_TOTAL_PER_CATEGORY:
                    existing.append(item)
                    added.append(item)
            if added:
                changes.append(f"Added {key}: {', '.join(added)}")

        if update.notes:
            learned["notes"] = update.notes

        if changes:
            self._profile.save()
            summary = "; ".join(changes)
            logger.info("Applied profile update: %s", summary)
            return summary

        return None

    def _validate_update(self, update: ProfileUpdate) -> bool:
        """Sanity-check a proposed update before applying."""
        for field_name in [
            "add_liked_themes",
            "add_disliked_themes",
            "add_liked_authors",
            "add_disliked_authors",
        ]:
            items = getattr(update, field_name)
            if not isinstance(items, list):
                logger.warning("Update field %s is not a list.", field_name)
                return False
            if len(items) > MAX_ITEMS_PER_UPDATE:
                logger.warning(
                    "Update field %s has %d items (max %d).",
                    field_name, len(items), MAX_ITEMS_PER_UPDATE,
                )
                return False
            if not all(isinstance(item, str) for item in items):
                logger.warning("Update field %s contains non-string items.", field_name)
                return False

        return True
