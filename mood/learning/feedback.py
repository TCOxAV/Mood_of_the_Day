"""Feedback processing — records user reactions and triggers learning.

When a user likes/dislikes a quote, this module:
1. Records the feedback in the profile.
2. Optionally triggers a profile update via the learning manager.
"""

from __future__ import annotations

import logging
from typing import Optional

from mood.learning.profile import UserProfile

logger = logging.getLogger(__name__)


class FeedbackProcessor:
    """Handles user feedback on displayed quotations."""

    def __init__(self, profile: UserProfile) -> None:
        self._profile = profile

    def record(self, quote_id: str, liked: bool, comment: str = "") -> None:
        """Record a feedback entry and save the profile."""
        self._profile.add_feedback(quote_id, liked=liked, comment=comment)
        self._profile.save()
        logger.info(
            "Recorded %s for quote %s",
            "like" if liked else "dislike",
            quote_id,
        )

    def should_trigger_learning(self) -> bool:
        """Return True if enough feedback has accumulated to warrant
        a learning update.

        We trigger after every 5 feedback entries to avoid excessive
        API calls while still being responsive.
        """
        history = self._profile.data.get("feedback_history", [])
        return len(history) > 0 and len(history) % 5 == 0
