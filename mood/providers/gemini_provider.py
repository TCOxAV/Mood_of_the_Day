"""Gemini provider — feedback analysis and profile learning.

Uses Google's ``google-genai`` SDK to:
1. Review user feedback and propose structured profile updates.
2. Select quotes when OpenAI is unavailable (fallback role).

Like OpenAI, all output is treated as untrusted and validated.
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

_MODEL = "gemini-2.0-flash"
_TIMEOUT = 30

class GeminiProvider(BaseProvider):
    """AI provider backed by Google Gemini."""

    @property
    def name(self) -> str:
        return "Gemini"

    def is_configured(self) -> bool:
        return bool(get_api_key("gemini"))

    def _get_client(self):
        """Create a Gemini client. Deferred import."""
        from google import genai

        key = get_api_key("gemini")
        if not key:
            raise ProviderError("Gemini API key not configured.")
        return genai.Client(api_key=key)

    async def test_connection(self) -> bool:
        """Verify the key by listing models."""
        try:
            client = self._get_client()
            list(client.models.list())
            return True
        except Exception as exc:
            logger.warning("Gemini connection test failed: %s", exc)
            return False

    async def select_quote(
        self,
        available_quotes: list[dict[str, Any]],
        user_preferences: str,
        exclude_ids: set[str],
    ) -> QuoteSelection:
        """Ask Gemini to select a quote (used when OpenAI is unavailable)."""
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

        prompt = (
            "You are a thoughtful literary curator. Pick ONE quotation from "
            "the list below that would resonate with this user today, and "
            "write a short personalized commentary (2-3 sentences).\n\n"
            f"User preferences:\n{user_preferences}\n\n"
            f"Available quotations:\n{json.dumps(quote_list, indent=1)}\n\n"
            "Respond ONLY with valid JSON:\n"
            '{"quote_id": "<id>", "commentary": "<commentary>"}\n\n'
            "Pick only from the list. Do not invent quotes."
        )

        try:
            client = self._get_client()
            response = client.models.generate_content(
                model=_MODEL,
                contents=prompt,
                config={
                    "temperature": 0.7,
                    "max_output_tokens": 300,
                },
            )

            content = response.text
            if not content:
                raise ProviderError("Gemini returned empty response.")

            content = content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                content = content.strip()

            result = json.loads(content)

            quote_id = result.get("quote_id", "")
            commentary = result.get("commentary", "")

            if not quote_id or not commentary:
                raise ProviderError("Gemini response missing required fields.")

            valid_ids = {q["id"] for q in quote_list}
            if quote_id not in valid_ids:
                raise ProviderError(
                    f"Gemini returned unknown quote_id: {quote_id!r}"
                )

            return QuoteSelection(quote_id=quote_id, commentary=commentary)

        except json.JSONDecodeError as exc:
            raise ProviderError(f"Gemini returned invalid JSON: {exc}") from exc
        except ProviderError:
            raise
        except Exception as exc:
            retryable = "rate" in str(exc).lower() or "quota" in str(exc).lower()
            raise ProviderError(
                f"Gemini API error: {exc}", retryable=retryable
            ) from exc

    async def update_profile(
        self,
        feedback_summary: dict[str, Any],
        user_preferences: str,
    ) -> Optional[ProfileUpdate]:
        """Gemini's primary role: analyze feedback and propose profile updates.

        Returns a structured proposal — never modifies files directly.
        """
        prompt = (
            "You are a personalization assistant. Analyze the user's feedback "
            "summary and current preferences, then suggest specific updates "
            "to improve future quotation selections.\n\n"
            f"Current preferences:\n{user_preferences}\n\n"
            f"Feedback summary:\n{json.dumps(feedback_summary, indent=1)}\n\n"
            "Respond ONLY with valid JSON:\n"
            "{\n"
            '  "add_liked_themes": ["theme1"],\n'
            '  "add_disliked_themes": [],\n'
            '  "add_liked_authors": [],\n'
            '  "add_disliked_authors": [],\n'
            '  "notes": "Brief explanation of why these changes are suggested"\n'
            "}\n\n"
            "Rules:\n"
            "- Only suggest changes clearly supported by the feedback data.\n"
            "- Use empty lists if no change is warranted for a category.\n"
            "- Keep theme/author names short and consistent.\n"
            "- Do not reference API keys or technical details."
        )

        try:
            client = self._get_client()
            response = client.models.generate_content(
                model=_MODEL,
                contents=prompt,
                config={
                    "temperature": 0.3,
                    "max_output_tokens": 300,
                },
            )

            content = response.text
            if not content:
                return None

            content = content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                content = content.strip()

            result = json.loads(content)

            update = ProfileUpdate(
                add_liked_themes=_ensure_str_list(result.get("add_liked_themes", [])),
                add_disliked_themes=_ensure_str_list(result.get("add_disliked_themes", [])),
                add_liked_authors=_ensure_str_list(result.get("add_liked_authors", [])),
                add_disliked_authors=_ensure_str_list(result.get("add_disliked_authors", [])),
                notes=str(result.get("notes", "")),
            )
            return update

        except Exception as exc:
            logger.warning("Gemini profile update failed: %s", exc)
            return None

def _ensure_str_list(value: Any) -> list[str]:
    """Coerce a value to a list of strings, discarding non-strings."""
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, (str, int, float))]
