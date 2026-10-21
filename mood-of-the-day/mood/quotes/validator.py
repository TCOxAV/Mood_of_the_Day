"""Schema validation for quotation records and cache entries.

Every piece of JSON that enters the system — whether from disk or an
AI provider — passes through validators here before being trusted.
This is the single enforcement point for data integrity.
"""

from __future__ import annotations

from typing import Any

_QUOTE_SCHEMA: dict[str, type] = {
    "id": str,
    "text": str,
    "author": str,
    "source": str,
    "themes": list,
    "verified": bool,
}

_CACHE_ENTRY_SCHEMA: dict[str, type] = {
    "quote_id": str,
    "text": str,
    "author": str,
    "source": str,
    "commentary": str,
    "date": str,
    "themes": list,
    "verified": bool,
}

MAX_TEXT_LENGTH = 2000
MAX_COMMENTARY_LENGTH = 1500
MAX_THEMES = 20

class ValidationError(Exception):
    """Raised when a data structure fails schema validation."""

def validate_quote(data: Any) -> dict:
    """Validate a single quotation record from the library.

    Returns the validated dict or raises ``ValidationError``.
    """
    if not isinstance(data, dict):
        raise ValidationError(f"Expected dict, got {type(data).__name__}")

    for field, expected_type in _QUOTE_SCHEMA.items():
        if field not in data:
            raise ValidationError(f"Missing required field: {field!r}")
        if not isinstance(data[field], expected_type):
            raise ValidationError(
                f"Field {field!r}: expected {expected_type.__name__}, "
                f"got {type(data[field]).__name__}"
            )

    if len(data["text"]) > MAX_TEXT_LENGTH:
        raise ValidationError(
            f"Quote text too long ({len(data['text'])} chars, max {MAX_TEXT_LENGTH})"
        )
    if not data["text"].strip():
        raise ValidationError("Quote text is empty")
    if not data["author"].strip():
        raise ValidationError("Author is empty")
    if len(data["themes"]) > MAX_THEMES:
        raise ValidationError(f"Too many themes ({len(data['themes'])})")

    return data

def validate_cache_entry(data: Any) -> dict:
    """Validate a single cache entry.

    Returns the validated dict or raises ``ValidationError``.
    """
    if not isinstance(data, dict):
        raise ValidationError(f"Expected dict, got {type(data).__name__}")

    for field, expected_type in _CACHE_ENTRY_SCHEMA.items():
        if field not in data:
            raise ValidationError(f"Missing required field: {field!r}")
        if not isinstance(data[field], expected_type):
            raise ValidationError(
                f"Field {field!r}: expected {expected_type.__name__}, "
                f"got {type(data[field]).__name__}"
            )

    if len(data["text"]) > MAX_TEXT_LENGTH:
        raise ValidationError("Quote text too long")
    if len(data["commentary"]) > MAX_COMMENTARY_LENGTH:
        raise ValidationError("Commentary too long")

    date_str = data["date"]
    if len(date_str) != 10 or date_str[4] != "-" or date_str[7] != "-":
        raise ValidationError(f"Invalid date format: {date_str!r} (expected YYYY-MM-DD)")

    return data

def validate_quote_library(data: Any) -> dict:
    """Validate the entire quotes library JSON structure."""
    if not isinstance(data, dict):
        raise ValidationError("Library root must be a dict")
    if "version" not in data or "quotes" not in data:
        raise ValidationError("Library must have 'version' and 'quotes' keys")
    if not isinstance(data["quotes"], list):
        raise ValidationError("'quotes' must be a list")

    seen_ids: set[str] = set()
    for i, quote in enumerate(data["quotes"]):
        try:
            validate_quote(quote)
        except ValidationError as exc:
            raise ValidationError(f"Quote at index {i}: {exc}") from exc

        if quote["id"] in seen_ids:
            raise ValidationError(f"Duplicate quote ID: {quote['id']!r}")
        seen_ids.add(quote["id"])

    return data
