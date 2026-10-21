"""Abstract base class for AI providers.

Defines the contract that OpenAI, Gemini, and any future providers
must implement. The application code only depends on this interface,
never on a specific provider's SDK.

Design decision: two distinct capabilities.
  1. select_quote() — pick a quote from the library and write commentary.
  2. update_profile() — review feedback and propose profile changes.

A provider may implement one or both. If only one provider is
configured, it handles both tasks.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class QuoteSelection:
    """The result of an AI-assisted quote selection.

    The provider picks a quote ID from the library and generates
    personalized commentary. The quote text itself comes from the
    library — never from the AI.
    """
    quote_id: str
    commentary: str
    confidence: float = 1.0

@dataclass
class ProfileUpdate:
    """A structured proposal to update the user's learning profile.

    Gemini proposes these; the application validates and applies them.
    The provider never gets direct filesystem access.
    """
    add_liked_themes: list[str]
    add_disliked_themes: list[str]
    add_liked_authors: list[str]
    add_disliked_authors: list[str]
    notes: str = ""

class ProviderError(Exception):
    """Raised when a provider call fails (network, auth, rate limit, etc.)."""

    def __init__(self, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable

class BaseProvider(ABC):
    """Interface that all AI providers must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name (e.g. 'OpenAI', 'Gemini')."""
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if this provider has a valid API key."""
        ...

    @abstractmethod
    async def test_connection(self) -> bool:
        """Verify that the API key works. Return True on success."""
        ...

    @abstractmethod
    async def select_quote(
        self,
        available_quotes: list[dict[str, Any]],
        user_preferences: str,
        exclude_ids: set[str],
    ) -> QuoteSelection:
        """Choose a quote and generate personalized commentary.

        Args:
            available_quotes: List of quote dicts from the library.
            user_preferences: Compact preference summary string.
            exclude_ids: Quote IDs to avoid (recently shown).

        Returns:
            A ``QuoteSelection`` with the chosen quote ID and commentary.

        Raises:
            ProviderError: On API failure.
        """
        ...

    @abstractmethod
    async def update_profile(
        self,
        feedback_summary: dict[str, Any],
        user_preferences: str,
    ) -> Optional[ProfileUpdate]:
        """Review feedback and propose profile changes.

        Args:
            feedback_summary: Compact feedback stats (never full history).
            user_preferences: Current preference summary.

        Returns:
            A ``ProfileUpdate`` proposal, or None if no changes needed.

        Raises:
            ProviderError: On API failure.
        """
        ...
