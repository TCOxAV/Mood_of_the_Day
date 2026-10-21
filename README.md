# Mood of the Day (Beta-Linux Only)

> **Beta Testing:** Mood of the Day is currently in active Beta testing across Linux distributions and desktop environments (GNOME, KDE Plasma, XFCE). If you test the app, please share your thoughts and issues in our **[Feedback & Testing Form](Paste your Google Form link here)**!

A lightweight Linux desktop application that greets you each morning with a
famous quotation personalized to your interests, personality, and feedback.

## Features

- **Personalized quotations** — learns your preferences over time
- **AI-powered selection** — uses OpenAI and/or Google Gemini to pick and
  explain quotations that resonate with you
- **Works offline** — displays cached quotations when no API is available
- **Five-day rolling cache** — pre-generates quotations to minimize API calls
- **Privacy-first** — API keys stored in your system keyring, minimal data
  sent to providers, no telemetry
- **XDG Autostart** — optionally opens automatically when you log in

## Requirements

- Python 3.10+
- Linux with a graphical desktop (X11 or Wayland: GNOME, KDE Plasma, XFCE, Sway, Hyprland, etc.)
- PySide6 (Qt 6)
- System graphics libraries (`libxkbcommon`, `libgl`/`libglvnd`, `libEGL` — see [SETUP.md](SETUP.md) for distro package managers: `apt`, `pacman`, `dnf`, `zypper`, `apk`)

Optional:
- An OpenAI API key (for quotation selection and commentary)
- A Google Gemini API key (for profile learning)
- A system keyring (GNOME Keyring, KWallet, etc.) for secure key storage

> **Note:** An OpenAI API key requires separate API billing at
> <https://platform.openai.com/account/billing>. A ChatGPT subscription does
> **not** include API credits.

## Quick Start

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/mood-of-the-day.git
cd mood-of-the-day

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e ".[dev]"

# Run the application
python -m mood.main
```

For detailed setup options, troubleshooting, display server configs, and **Docker instructions**, see [SETUP.md](SETUP.md).

## Installation (User-Level Autostart)

```bash
# Install the desktop entry for your user (no root required)
bash scripts/install.sh

# To remove autostart
bash scripts/uninstall.sh
```

## Configuration

On first launch, the setup wizard asks for:
- Your preferred name
- API keys (optional — the app works without them)
- Your personality, interests, preferred tone, and themes

All user data is stored under `~/.local/share/mood-of-the-day/` and
`~/.config/mood-of-the-day/` (following the XDG Base Directory specification
via `platformdirs`).

API keys are stored in your system keyring when available. If no keyring
backend is found, keys are stored in a file with restricted permissions
(`0600`) under `~/.config/mood-of-the-day/`. A warning is displayed in this
case.

## Project Structure

```
mood-of-the-day/
├── mood/                   # Application package
│   ├── main.py             # Entry point
│   ├── setup.py            # First-run setup wizard
│   ├── popup.py            # Daily quotation popup window
│   ├── settings.py         # Settings/preferences UI
│   ├── providers/          # AI provider abstraction
│   │   ├── base.py         # Abstract provider interface
│   │   ├── openai_provider.py
│   │   └── gemini_provider.py
│   ├── quotes/             # Quotation library and selection
│   │   ├── library.py      # Load/query the quotes library
│   │   ├── selector.py     # AI-assisted quote selection
│   │   └── validator.py    # Validate quote structures
│   ├── learning/           # Personalization engine
│   │   ├── profile.py      # User profile schema and I/O
│   │   ├── feedback.py     # Feedback processing
│   │   └── manager.py      # Learning manager (Gemini integration)
│   ├── storage/            # Persistence layer
│   │   ├── config.py       # Application configuration
│   │   ├── cache.py        # Five-day rolling cache
│   │   └── paths.py        # XDG-compliant paths
│   └── system/             # OS integration
│       └── autostart.py    # XDG autostart desktop entry
├── data/
│   └── quotes.json         # Curated, verified quotation library
├── tests/                  # Automated tests (pytest)
├── scripts/
│   ├── install.sh          # User-level install script
│   └── uninstall.sh        # Uninstall script
├── pyproject.toml          # Project metadata and build config
├── requirements.txt        # Pinned dependencies
└── LICENSE                 # MIT License
```

## Running Tests

```bash
# Run all tests (no API keys required — calls are mocked)
pytest

# Run with verbose output
pytest -v

# Run a specific test module
pytest tests/test_cache.py
```

## How Personalization Works

1. Your profile (interests, personality, tone preferences) is stored locally.
2. When a quotation is displayed, you can **like** or **dislike** it.
3. Feedback is recorded locally and summarized (never sent in full to any API).
4. Gemini (if configured) proposes structured updates to your preference
   profile. Each proposal is validated against a schema before being applied.
5. Future quotation selections incorporate your learned preferences.

The AI providers **do not** permanently learn from your requests. All
personalization is managed by the application through local data.

## Privacy and Security

- API keys are **never** committed to Git, logged, or sent to another provider.
- Only compact preference summaries are sent to APIs — never your full
  feedback history.
- AI output is treated as untrusted data and validated before use.
- No AI-generated code or shell commands are executed.
- Cache and profile writes are atomic to prevent data corruption.

## Desktop Environment Support

The XDG autostart integration has been tested on GNOME. It should work on
KDE Plasma, XFCE, and other XDG-compliant desktop environments, but behavior
may vary.

If autostart doesn't work on your desktop environment, you can start the
application manually:

```bash
python -m mood.main
```

Or add the command to your desktop environment's startup applications
configuration.

## License

MIT License — see [LICENSE](LICENSE) for details.
