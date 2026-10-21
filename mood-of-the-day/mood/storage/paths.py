"""XDG-compliant paths for all application data.

Every module that reads or writes user files imports paths from here.
This gives us a single place to change if we ever need to support
a different OS or a custom data directory.

Uses platformdirs so we automatically get:
  - ~/.local/share/mood-of-the-day/   (user data: profile, cache)
  - ~/.config/mood-of-the-day/        (config: key fallback file)
"""

from __future__ import annotations

from pathlib import Path

from platformdirs import user_config_dir, user_data_dir

from mood import __app_name__

DATA_DIR = Path(user_data_dir(__app_name__))
CONFIG_DIR = Path(user_config_dir(__app_name__))

PROFILE_PATH = DATA_DIR / "profile.json"
CACHE_PATH = DATA_DIR / "cache.json"
PROFILE_BACKUP_PATH = DATA_DIR / "profile.backup.json"
KEY_FALLBACK_PATH = CONFIG_DIR / "keys.json"

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
QUOTES_LIBRARY_PATH = _REPO_ROOT / "data" / "quotes.json"

def ensure_dirs() -> None:
    """Create application directories if they don't exist.

    Called once at startup. Permissions are set so only the current
    user can read the config directory (where key fallback lives).
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.chmod(0o700)
