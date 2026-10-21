"""OpenAI provider — quote selection and commentary generation.

Uses the OpenAI Chat Completions API (openai>=1.30) to:
1. Pick the most appropriate quote from the library for the user.
2. Generate a short, personalized commentary explaining why it fits.

The model is asked to return structured JSON. All output is treated
as untrusted and validated before use.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from mood.providers.base import (
    BaseProvider,
    ProfileUpdate,
    ProviderError,
    QuoteSelection,
)
from mood.storage.config import get_api_key

logger = logging.getLogger(__name__)

_MODEL = "gpt-4o-mini"
_TIMEOUT = 30

class OpenAIProvider(BaseProvider):
    """AI provider backed by the OpenAI API."""

    @property
    def name(self) -> str:
        return "OpenAI"

    def is_configured(self) -> bool:
        return bool(get_api_key("openai"))

    def _get_client(self):
        """Create an OpenAI client. Import is deferred so the app
        starts even if the SDK has import-time issues."""
        from openai import OpenAI

        key = get_api_key("openai")
        if not key:
            raise ProviderError("OpenAI API key not configured.")
        return OpenAI(api_key=key, timeout=_TIMEOUT)

    async def test_connection(self) -> bool:
        """Verify the API key by listing models."""
        try:
            client = self._get_client()
            client.models.list()
            return True
        except Exception as exc:
            logger.warning("OpenAI connection test failed: %s", exc)
            return False

    async def select_quote(
        self,
        available_quotes: list[dict[str, Any]],
        user_preferences: str,
        exclude_ids: set[str],
    ) -> QuoteSelection:
        """Ask OpenAI to pick a quote and write commentary."""
        quote_list = [
            {
                "id": q["id"],
                "text": q["text"],
                "author": q["author"],
                "themes": q.get("themes", []),
            }
            for q in available_quotes
            if q["id"] not in exclude_ids
        ]

        if not quote_list:
            raise ProviderError("No available quotes to select from.")

        system_prompt = (
            "You are a thoughtful literary curator. The user has a profile "
            "describing their personality and interests. Your job is to pick "
            "ONE quotation from the provided list that would resonate with "
            "them today, and write a short, warm, personalized commentary "
            "(2-3 sentences) explaining why this quote is meaningful for them.\n\n"
            "Respond ONLY with valid JSON in this exact format:\n"
            '{"quote_id": "<id from the list>", "commentary": "<your commentary>"}\n\n'
            "Rules:\n"
            "- Pick only from the provided list. Do not invent quotes.\n"
            "- Do not modify the quote text.\n"
            "- Keep commentary concise and personal.\n"
            "- Do not mention the user's API keys or any technical details."
        )

        user_prompt = (
            f"User preferences:\n{user_preferences}\n\n"
            f"Available quotations:\n{json.dumps(quote_list, indent=1)}"
        )

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=300,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if not content:
                raise ProviderError("OpenAI returned empty response.")

            result = json.loads(content)

            quote_id = result.get("quote_id", "")
            commentary = result.get("commentary", "")

            if not quote_id or not commentary:
                raise ProviderError("OpenAI response missing required fields.")

            valid_ids = {q["id"] for q in quote_list}
            if quote_id not in valid_ids:
                raise ProviderError(
                    f"OpenAI returned unknown quote_id: {quote_id!r}"
                )

            return QuoteSelection(quote_id=quote_id, commentary=commentary)

        except json.JSONDecodeError as exc:
            raise ProviderError(f"OpenAI returned invalid JSON: {exc}") from exc
        except ProviderError:
            raise
        except Exception as exc:
            retryable = "rate" in str(exc).lower() or "timeout" in str(exc).lower()
            raise ProviderError(
                f"OpenAI API error: {exc}", retryable=retryable
            ) from exc

    async def update_profile(
        self,
        feedback_summary: dict[str, Any],
        user_preferences: str,
    ) -> Optional[ProfileUpdate]:
        """OpenAI can also update the profile if Gemini is unavailable.

        Uses the same structured-output approach.
        """
        system_prompt = (
            "You are a personalization assistant. Based on the user's "
            "feedback summary and current preferences, suggest updates "
            "to their preference profile.\n\n"
            "Respond ONLY with valid JSON:\n"
            "{\n"
            '  "add_liked_themes": ["theme1"],\n'
            '  "add_disliked_themes": [],\n'
            '  "add_liked_authors": [],\n'
            '  "add_disliked_authors": [],\n'
            '  "notes": "brief explanation"\n'
            "}\n\n"
            "Only suggest changes supported by the feedback. "
            "If no changes are warranted, return empty lists and "
            'set notes to "No changes needed."'
        )

        user_prompt = (
            f"Current preferences:\n{user_preferences}\n\n"
            f"Feedback summary:\n{json.dumps(feedback_summary, indent=1)}"
        )

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=200,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if not content:
                return None

            result = json.loads(content)
            return ProfileUpdate(
                add_liked_themes=result.get("add_liked_themes", []),
                add_disliked_themes=result.get("add_disliked_themes", []),
                add_liked_authors=result.get("add_liked_authors", []),
                add_disliked_authors=result.get("add_disliked_authors", []),
                notes=result.get("notes", ""),
            )

        except Exception as exc:
            logger.warning("OpenAI profile update failed: %s", exc)
            return None
