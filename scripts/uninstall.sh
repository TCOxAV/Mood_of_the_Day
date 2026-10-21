#!/usr/bin/env bash

set -euo pipefail

echo "=== Mood of the Day — Uninstall ==="
echo ""

AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/mood-of-the-day.desktop"

if [ -f "$DESKTOP_FILE" ]; then
    rm "$DESKTOP_FILE"
    echo "✓ Removed autostart entry."
else
    echo "  No autostart entry found."
fi

DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/mood-of-the-day"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/mood-of-the-day"

echo ""
echo "User data directories:"
echo "  $DATA_DIR"
echo "  $CONFIG_DIR"
echo ""
read -p "Remove user data? (y/N) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    [ -d "$DATA_DIR" ] && rm -rf "$DATA_DIR" && echo "  ✓ Removed $DATA_DIR"
    [ -d "$CONFIG_DIR" ] && rm -rf "$CONFIG_DIR" && echo "  ✓ Removed $CONFIG_DIR"
else
    echo "  User data preserved."
fi

echo ""
echo "✓ Uninstall complete."
echo "  Note: The virtual environment and source code were not removed."
echo "  Delete the project directory manually if you no longer need it."
