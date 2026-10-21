"""XDG autostart integration for Linux desktop sessions.

Creates/removes a .desktop entry in ~/.config/autostart/ so the
application starts automatically when the user logs in.

No root privileges required — this only touches user-level files.
"""

from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_AUTOSTART_DIR = Path.home() / ".config" / "autostart"
_DESKTOP_FILENAME = "mood-of-the-day.desktop"
_DESKTOP_FILE_PATH = _AUTOSTART_DIR / _DESKTOP_FILENAME


def _desktop_entry_content() -> str:
    """Generate the .desktop file content."""
    python = sys.executable or shutil.which("python3") or "python3"
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Mood of the Day\n"
        "Comment=Your daily personalized quotation\n"
        f"Exec={python} -m mood.main\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
        "StartupNotify=false\n"
        "Categories=Utility;\n"
    )


def install_autostart() -> bool:
    """Install the XDG autostart .desktop entry.

    Returns True on success, False on failure.
    """
    try:
        _AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
        _DESKTOP_FILE_PATH.write_text(
            _desktop_entry_content(), encoding="utf-8"
        )
        logger.info("Autostart installed: %s", _DESKTOP_FILE_PATH)
        return True
    except OSError as exc:
        logger.error("Failed to install autostart: %s", exc)
        return False


def uninstall_autostart() -> bool:
    """Remove the autostart .desktop entry.

    Returns True if removed (or already absent), False on error.
    """
    if not _DESKTOP_FILE_PATH.exists():
        return True
    try:
        _DESKTOP_FILE_PATH.unlink()
        logger.info("Autostart removed: %s", _DESKTOP_FILE_PATH)
        return True
    except OSError as exc:
        logger.error("Failed to remove autostart: %s", exc)
        return False


def is_autostart_installed() -> bool:
    """Check whether the autostart entry exists."""
    return _DESKTOP_FILE_PATH.exists()
