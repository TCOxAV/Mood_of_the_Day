"""Quote selection orchestrator.

Coordinates between the quote library, AI providers, and the cache
to produce a daily quotation. This is the core business logic that
ties providers to data.

Selection priority:
1. If a provider is available → AI-assisted selection
2. If no provider → random verified fallback from the library
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional

from mood.learning.profile import UserProfile
from mood.providers.base import BaseProvider, ProviderError, QuoteSelection
from mood.quotes.library import Quote, QuoteLibrary
from mood.storage.cache import DailyCache

logger = logging.getLogger(__name__)

class QuoteSelector:
    """Selects and caches daily quotations."""

    def __init__(
        self,
        library: QuoteLibrary,
        cache: DailyCache,
        profile: UserProfile,
        selection_provider: Optional[BaseProvider] = None,
    ) -> None:
        self._library = library
        self._cache = cache
        self._profile = profile
        self._provider = selection_provider

    async def get_today(self) -> dict[str, Any]:
        """Get today's quotation entry.

        Returns a cache-format dict. Uses cache if available,
        otherwise generates via AI or falls back to the library.
        """
        today = date.today().isoformat()

        cached = self._cache.get_entry(today)
        if cached:
            return cached

        if self._provider and self._provider.is_configured():
            try:
                entry = await self._generate_entry(today)
                if entry:
                    self._cache.set_entry(today, entry)
                    self._cache.save()
                    self._profile.add_recent_quote(entry["quote_id"])
                    self._profile.save()
                    return entry
            except (ProviderError, Exception) as exc:
                logger.warning("AI selection failed, using fallback: %s", exc)

        return self._fallback_entry(today)

    async def _generate_entry(self, iso_date: str) -> Optional[dict[str, Any]]:
        """Use the AI provider to generate a cache entry for one date."""
        if not self._provider:
            return None

        exclude_ids = self._cache.cached_quote_ids() | set(self._profile.recent_quote_ids)
        quotes_data = [
            {
                "id": q.id,
                "text": q.text,
                "author": q.author,
                "source": q.source,
                "themes": list(q.themes),
                "verified": q.verified,
            }
            for q in self._library.all_quotes()
        ]

        preferences = self._profile.get_preference_summary()

        selection: QuoteSelection = await self._provider.select_quote(
            available_quotes=quotes_data,
            user_preferences=preferences,
            exclude_ids=exclude_ids,
        )

        quote = self._library.get(selection.quote_id)
        if not quote:
            logger.warning(
                "Provider returned unknown quote ID %r, ignoring.",
                selection.quote_id,
            )
            return None

        return _build_cache_entry(quote, selection.commentary, iso_date)

    def _fallback_entry(self, iso_date: str) -> dict[str, Any]:
        """Build a cache entry from a random library quote (no AI)."""
        exclude_ids = self._cache.cached_quote_ids()
        quote = self._library.random_fallback(exclude_ids=exclude_ids)

        if not quote:
            quote = Quote(
                id="fallback-000",
                text="The unexamined life is not worth living.",
                author="Socrates",
                source="Plato's Apology (399 BC)",
                themes=("philosophy", "wisdom"),
                verified=True,
                notes="Hardcoded fallback.",
            )

        commentary = (
            f"Here's a thought from {quote.author} to start your day. "
            "(Shown as a fallback — connect an AI provider for personalized selections.)"
        )

        entry = _build_cache_entry(quote, commentary, iso_date, is_fallback=True)

        try:
            self._cache.set_entry(iso_date, entry)
            self._cache.save()
        except Exception as exc:
            logger.warning("Failed to cache fallback entry: %s", exc)

        return entry

    async def fill_cache(self) -> int:
        """Fill missing dates in the 5-day cache window.

        Returns the number of entries generated.
        """
        missing = self._cache.missing_dates()
        if not missing or not self._provider or not self._provider.is_configured():
            return 0

        generated = 0
        for iso_date in missing:
            try:
                entry = await self._generate_entry(iso_date)
                if entry:
                    self._cache.set_entry(iso_date, entry)
                    generated += 1
            except (ProviderError, Exception) as exc:
                logger.warning("Failed to generate cache for %s: %s", iso_date, exc)
                break

        if generated:
            self._cache.save()
            logger.info("Filled %d cache entries.", generated)

        return generated

    async def regenerate_today(self) -> Optional[dict[str, Any]]:
        """Force-regenerate today's entry (user clicked refresh)."""
        today = date.today().isoformat()

        if self._provider and self._provider.is_configured():
            try:
                entry = await self._generate_entry(today)
                if entry:
                    self._cache.set_entry(today, entry)
                    self._cache.save()
                    self._profile.add_recent_quote(entry["quote_id"])
                    self._profile.save()
                    return entry
            except Exception as exc:
                logger.warning("Regeneration failed: %s", exc)

        return self._fallback_entry(today)

def _build_cache_entry(
    quote: Quote,
    commentary: str,
    iso_date: str,
    is_fallback: bool = False,
) -> dict[str, Any]:
    """Build a validated cache entry dict."""
    return {
        "quote_id": quote.id,
        "text": quote.text,
        "author": quote.author,
        "source": quote.source,
        "commentary": commentary,
        "date": iso_date,
        "themes": list(quote.themes),
        "verified": quote.verified,
        "is_fallback": is_fallback,
    }
