#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Mood of the Day — Install ==="
echo ""

if [ ! -d "$PROJECT_DIR/.venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$PROJECT_DIR/.venv"
fi

echo "Installing dependencies..."
"$PROJECT_DIR/.venv/bin/pip" install --quiet -e "$PROJECT_DIR[dev]"

AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/mood-of-the-day.desktop"

mkdir -p "$AUTOSTART_DIR"

PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Type=Application
Name=Mood of the Day
Comment=Your daily personalized quotation
Exec=$PYTHON_BIN -m mood.main
Terminal=false
X-GNOME-Autostart-enabled=true
StartupNotify=false
Categories=Utility;
EOF

echo ""
echo "✓ Installed successfully!"
echo "  Autostart entry: $DESKTOP_FILE"
echo "  Python: $PYTHON_BIN"
echo ""
echo "To run now:  $PYTHON_BIN -m mood.main"
echo "The app will also start automatically on your next login."
