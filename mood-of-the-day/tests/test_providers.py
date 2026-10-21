"""Tests for AI provider error handling (mocked — no real API calls)."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mood.providers.base import ProviderError, QuoteSelection, ProfileUpdate
from mood.providers.openai_provider import OpenAIProvider
from mood.providers.gemini_provider import GeminiProvider

SAMPLE_QUOTES = [
    {
        "id": "test-001",
        "text": "Test quote one.",
        "author": "Author A",
        "source": "Source A",
        "themes": ["wisdom"],
        "verified": True,
    },
    {
        "id": "test-002",
        "text": "Test quote two.",
        "author": "Author B",
        "source": "Source B",
        "themes": ["courage"],
        "verified": True,
    },
]

class TestOpenAIProvider:
    """Tests for OpenAI provider with mocked SDK."""

    @patch("mood.providers.openai_provider.get_api_key", return_value="sk-test-key")
    def test_is_configured(self, mock_key):
        provider = OpenAIProvider()
        assert provider.is_configured() is True

    @patch("mood.providers.openai_provider.get_api_key", return_value=None)
    def test_not_configured(self, mock_key):
        provider = OpenAIProvider()
        assert provider.is_configured() is False

    @patch("mood.providers.openai_provider.get_api_key", return_value="sk-test-key")
    def test_select_quote_success(self, mock_key):
        """Test successful quote selection with mocked OpenAI response."""
        provider = OpenAIProvider()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "quote_id": "test-001",
            "commentary": "This quote resonates with your curiosity.",
        })

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch.object(provider, "_get_client", return_value=mock_client):
            result = asyncio.run(
                provider.select_quote(SAMPLE_QUOTES, "Curious person", set())
            )

        assert isinstance(result, QuoteSelection)
        assert result.quote_id == "test-001"
        assert "curiosity" in result.commentary.lower()

    @patch("mood.providers.openai_provider.get_api_key", return_value="sk-test-key")
    def test_select_quote_invalid_id_rejected(self, mock_key):
        """Test that an unknown quote ID from OpenAI is rejected."""
        provider = OpenAIProvider()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "quote_id": "nonexistent-id",
            "commentary": "Commentary.",
        })

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch.object(provider, "_get_client", return_value=mock_client):
            with pytest.raises(ProviderError, match="unknown quote_id"):
                asyncio.run(
                    provider.select_quote(SAMPLE_QUOTES, "Test", set())
                )

    @patch("mood.providers.openai_provider.get_api_key", return_value="sk-test-key")
    def test_select_quote_empty_response(self, mock_key):
        """Test handling of empty API response."""
        provider = OpenAIProvider()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = ""

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch.object(provider, "_get_client", return_value=mock_client):
            with pytest.raises(ProviderError, match="empty"):
                asyncio.run(
                    provider.select_quote(SAMPLE_QUOTES, "Test", set())
                )

    @patch("mood.providers.openai_provider.get_api_key", return_value="sk-test-key")
    def test_select_quote_invalid_json(self, mock_key):
        """Test handling of malformed JSON from API."""
        provider = OpenAIProvider()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "not json at all"

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch.object(provider, "_get_client", return_value=mock_client):
            with pytest.raises(ProviderError, match="invalid JSON"):
                asyncio.run(
                    provider.select_quote(SAMPLE_QUOTES, "Test", set())
                )

    def test_select_quote_no_quotes_available(self):
        """Test error when all quotes are excluded."""
        provider = OpenAIProvider()
        with pytest.raises(ProviderError, match="No available quotes"):
            asyncio.run(
                provider.select_quote(
                    SAMPLE_QUOTES, "Test", {"test-001", "test-002"}
                )
            )

class TestGeminiProvider:
    """Tests for Gemini provider with mocked SDK."""

    @patch("mood.providers.gemini_provider.get_api_key", return_value="AIza-test")
    def test_is_configured(self, mock_key):
        provider = GeminiProvider()
        assert provider.is_configured() is True

    @patch("mood.providers.gemini_provider.get_api_key", return_value=None)
    def test_not_configured(self, mock_key):
        provider = GeminiProvider()
        assert provider.is_configured() is False

    @patch("mood.providers.gemini_provider.get_api_key", return_value="AIza-test")
    def test_select_quote_strips_code_fence(self, mock_key):
        """Test that Gemini's markdown-wrapped JSON is handled."""
        provider = GeminiProvider()

        fenced_json = (
            '```json\n'
            '{"quote_id": "test-002", "commentary": "Great quote for you."}\n'
            '```'
        )

        mock_response = MagicMock()
        mock_response.text = fenced_json

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch.object(provider, "_get_client", return_value=mock_client):
            result = asyncio.run(
                provider.select_quote(SAMPLE_QUOTES, "Test user", set())
            )

        assert result.quote_id == "test-002"

    @patch("mood.providers.gemini_provider.get_api_key", return_value="AIza-test")
    def test_update_profile_success(self, mock_key):
        """Test successful profile update proposal from Gemini."""
        provider = GeminiProvider()

        response_json = json.dumps({
            "add_liked_themes": ["stoicism"],
            "add_disliked_themes": [],
            "add_liked_authors": ["Marcus Aurelius"],
            "add_disliked_authors": [],
            "notes": "User shows strong preference for Stoic philosophy.",
        })

        mock_response = MagicMock()
        mock_response.text = response_json

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch.object(provider, "_get_client", return_value=mock_client):
            result = asyncio.run(
                provider.update_profile(
                    {"total_likes": 5, "total_dislikes": 1},
                    "Curious student",
                )
            )

        assert isinstance(result, ProfileUpdate)
        assert "stoicism" in result.add_liked_themes
        assert "Marcus Aurelius" in result.add_liked_authors

    @patch("mood.providers.gemini_provider.get_api_key", return_value="AIza-test")
    def test_update_profile_handles_failure(self, mock_key):
        """Test graceful handling of Gemini API failure."""
        provider = GeminiProvider()

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("API error")

        with patch.object(provider, "_get_client", return_value=mock_client):
            result = asyncio.run(
                provider.update_profile(
                    {"total_likes": 1},
                    "Test",
                )
            )

        assert result is None

class TestProviderInterface:
    """Tests verifying both providers implement the interface correctly."""

    def test_openai_has_required_methods(self):
        provider = OpenAIProvider()
        assert hasattr(provider, "name")
        assert hasattr(provider, "is_configured")
        assert hasattr(provider, "test_connection")
        assert hasattr(provider, "select_quote")
        assert hasattr(provider, "update_profile")

    def test_gemini_has_required_methods(self):
        provider = GeminiProvider()
        assert hasattr(provider, "name")
        assert hasattr(provider, "is_configured")
        assert hasattr(provider, "test_connection")
        assert hasattr(provider, "select_quote")
        assert hasattr(provider, "update_profile")

    def test_provider_names(self):
        assert OpenAIProvider().name == "OpenAI"
        assert GeminiProvider().name == "Gemini"
