"""Application configuration — API key management.

Handles two storage backends for API keys:
1. System keyring (GNOME Keyring, KWallet, etc.) — preferred.
2. Fallback JSON file with 0600 permissions — used when no
   usable keyring backend is available.

Keys are NEVER stored in the learning profile, logs, or Git.
"""

from __future__ import annotations

import json
import logging
import os
import stat
from typing import Optional

import keyring
from keyring.errors import (
    KeyringError,
    NoKeyringError,
)

from mood.storage.paths import KEY_FALLBACK_PATH, ensure_dirs

logger = logging.getLogger(__name__)

_SERVICE_NAME = "mood-of-the-day"
_KEYRING_AVAILABLE: bool | None = None

def _probe_keyring() -> bool:
    """Check whether a usable system keyring backend exists."""
    global _KEYRING_AVAILABLE
    if _KEYRING_AVAILABLE is not None:
        return _KEYRING_AVAILABLE
    try:
        keyring.get_password(_SERVICE_NAME, "__probe__")
        _KEYRING_AVAILABLE = True
    except (NoKeyringError, KeyringError, RuntimeError):
        _KEYRING_AVAILABLE = False
        logger.warning(
            "No usable system keyring found. "
            "API keys will be stored in %s with restricted permissions.",
            KEY_FALLBACK_PATH,
        )
    return _KEYRING_AVAILABLE

def _read_fallback() -> dict[str, str]:
    """Read the fallback key file, returning an empty dict on error."""
    if not KEY_FALLBACK_PATH.exists():
        return {}
    try:
        data = json.loads(KEY_FALLBACK_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read key fallback file: %s", exc)
    return {}

def _write_fallback(data: dict[str, str]) -> None:
    """Write the fallback key file with 0600 permissions."""
    ensure_dirs()
    tmp_path = KEY_FALLBACK_PATH.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )
    os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)
    tmp_path.replace(KEY_FALLBACK_PATH)

def store_api_key(provider: str, key: str) -> None:
    """Persist an API key for *provider* (e.g. 'openai', 'gemini').

    Uses the system keyring if available, otherwise the fallback file.
    """
    if _probe_keyring():
        try:
            keyring.set_password(_SERVICE_NAME, provider, key)
            return
        except KeyringError as exc:
            logger.warning("Keyring write failed, using fallback: %s", exc)

    data = _read_fallback()
    data[provider] = key
    _write_fallback(data)

def get_api_key(provider: str) -> Optional[str]:
    """Retrieve the stored API key for *provider*, or None."""
    if _probe_keyring():
        try:
            value = keyring.get_password(_SERVICE_NAME, provider)
            if value:
                return value
        except KeyringError as exc:
            logger.warning("Keyring read failed, trying fallback: %s", exc)

    return _read_fallback().get(provider)

def delete_api_key(provider: str) -> None:
    """Remove the stored API key for *provider*."""
    if _probe_keyring():
        try:
            keyring.delete_password(_SERVICE_NAME, provider)
        except KeyringError:
            pass

    data = _read_fallback()
    if provider in data:
        del data[provider]
        _write_fallback(data)

def has_any_provider() -> bool:
    """Return True if at least one API key is configured."""
    return bool(get_api_key("openai") or get_api_key("gemini"))

def is_keyring_available() -> bool:
    """Return True if a system keyring backend is usable."""
    return _probe_keyring()
