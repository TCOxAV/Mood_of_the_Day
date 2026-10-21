"""Daily quotation popup — the main UI the user sees.

Displays:
- A greeting with the user's name
- The quotation text, author, and source
- AI-generated personalized commentary
- Like / Dislike / Refresh / Close buttons
- Fallback indicator when applicable
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

class QuotePopup(QWidget):
    """The daily quotation popup window."""

    liked = Signal(str)
    disliked = Signal(str)
    refresh_requested = Signal()
    settings_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Mood of the Day")
        self.setMinimumSize(520, 420)
        self.setMaximumSize(700, 600)
        self.setStyleSheet(self._stylesheet())

        self._current_quote_id: str = ""
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 28, 32, 24)
        main_layout.setSpacing(0)

        header = QHBoxLayout()
        self._greeting = QLabel("Good morning! ☀️")
        self._greeting.setObjectName("greeting")
        header.addWidget(self._greeting)
        header.addStretch()

        settings_btn = QPushButton("⚙")
        settings_btn.setObjectName("iconBtn")
        settings_btn.setToolTip("Settings")
        settings_btn.setFixedSize(36, 36)
        settings_btn.clicked.connect(self.settings_requested.emit)
        header.addWidget(settings_btn)

        main_layout.addLayout(header)
        main_layout.addSpacing(20)

        card = QFrame()
        card.setObjectName("quoteCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(16)

        self._quote_text = QLabel()
        self._quote_text.setObjectName("quoteText")
        self._quote_text.setWordWrap(True)
        self._quote_text.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        card_layout.addWidget(self._quote_text)

        self._attribution = QLabel()
        self._attribution.setObjectName("attribution")
        self._attribution.setWordWrap(True)
        card_layout.addWidget(self._attribution)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("separator")
        card_layout.addWidget(sep)

        self._commentary = QLabel()
        self._commentary.setObjectName("commentary")
        self._commentary.setWordWrap(True)
        card_layout.addWidget(self._commentary)

        self._fallback_badge = QLabel("📋 Offline fallback")
        self._fallback_badge.setObjectName("fallbackBadge")
        self._fallback_badge.setVisible(False)
        card_layout.addWidget(self._fallback_badge)

        main_layout.addWidget(card)
        main_layout.addSpacing(16)

        actions = QHBoxLayout()
        actions.setSpacing(10)

        self._like_btn = QPushButton("👍 Like")
        self._like_btn.setObjectName("feedbackBtn")
        self._like_btn.clicked.connect(self._on_like)

        self._dislike_btn = QPushButton("👎 Not for me")
        self._dislike_btn.setObjectName("feedbackBtn")
        self._dislike_btn.clicked.connect(self._on_dislike)

        self._refresh_btn = QPushButton("🔄 New quote")
        self._refresh_btn.setObjectName("secondaryBtn")
        self._refresh_btn.clicked.connect(self.refresh_requested.emit)

        close_btn = QPushButton("✕ Close")
        close_btn.setObjectName("closeBtn")
        close_btn.clicked.connect(self.close)

        actions.addWidget(self._like_btn)
        actions.addWidget(self._dislike_btn)
        actions.addStretch()
        actions.addWidget(self._refresh_btn)
        actions.addWidget(close_btn)

        main_layout.addLayout(actions)

    def display_entry(self, entry: dict[str, Any], user_name: str = "") -> None:
        """Populate the popup with a cache entry."""
        self._current_quote_id = entry.get("quote_id", "")

        greeting = f"Good day, {user_name}! ☀️" if user_name else "Good day! ☀️"
        self._greeting.setText(greeting)

        text = entry.get("text", "")
        self._quote_text.setText(f"\u201c{text}\u201d")

        author = entry.get("author", "Unknown")
        source = entry.get("source", "")
        verified = entry.get("verified", False)
        attr_parts = [f"— {author}"]
        if source:
            attr_parts.append(f"  {source}")
        if verified:
            attr_parts.append("  ✓ Verified attribution")
        self._attribution.setText("\n".join(attr_parts))

        commentary = entry.get("commentary", "")
        self._commentary.setText(commentary)
        self._commentary.setVisible(bool(commentary))

        is_fallback = entry.get("is_fallback", False)
        self._fallback_badge.setVisible(is_fallback)

        self._like_btn.setEnabled(True)
        self._dislike_btn.setEnabled(True)
        self._like_btn.setText("👍 Like")
        self._dislike_btn.setText("👎 Not for me")

    def set_loading(self, loading: bool) -> None:
        """Show a loading state while fetching a new quote."""
        if loading:
            self._quote_text.setText("Finding a quote for you...")
            self._commentary.setText("")
            self._attribution.setText("")
            self._refresh_btn.setEnabled(False)
        else:
            self._refresh_btn.setEnabled(True)

    def _on_like(self) -> None:
        if self._current_quote_id:
            self._like_btn.setText("👍 Liked!")
            self._like_btn.setEnabled(False)
            self._dislike_btn.setEnabled(False)
            self.liked.emit(self._current_quote_id)

    def _on_dislike(self) -> None:
        if self._current_quote_id:
            self._dislike_btn.setText("👎 Noted")
            self._like_btn.setEnabled(False)
            self._dislike_btn.setEnabled(False)
            self.disliked.emit(self._current_quote_id)

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.close()
        elif key == Qt.Key.Key_L:
            self._on_like()
        elif key == Qt.Key.Key_D:
            self._on_dislike()
        elif key == Qt.Key.Key_R:
            self.refresh_requested.emit()
        else:
            super().keyPressEvent(event)

    @staticmethod
    def _stylesheet() -> str:
        return """
            QWidget {
                background-color: #1a1b2e;
                color: #e0e0e8;
                font-family: 'Inter', 'Segoe UI', sans-serif;
                font-size: 14px;
            }
            #greeting {
                font-size: 17px;
                font-weight: 600;
                color: #c4b5fd;
            }
            #quoteCard {
                background-color: #232444;
                border: 1px solid #3f3f6b;
                border-radius: 12px;
            }
            #quoteText {
                font-size: 18px;
                font-weight: 500;
                line-height: 1.6;
                color: #f0f0f5;
                font-style: italic;
            }
            #attribution {
                font-size: 13px;
                color: #a78bfa;
                font-weight: 600;
            }
            #separator {
                color: #3f3f6b;
                max-height: 1px;
            }
            #commentary {
                font-size: 13px;
                color: #9ca3af;
                line-height: 1.5;
            }
            #fallbackBadge {
                font-size: 11px;
                color: #fbbf24;
                padding: 4px 8px;
                background-color: rgba(251, 191, 36, 0.1);
                border-radius: 4px;
            }
            #feedbackBtn {
                background-color: #2d2e4a;
                border: 1px solid #3f3f6b;
                border-radius: 8px;
                padding: 8px 18px;
                color: #c4c4d4;
                font-weight: 600;
                font-size: 13px;
            }
            #feedbackBtn:hover {
                background-color: #3a3b5c;
                border-color: #a78bfa;
            }
            #feedbackBtn:disabled {
                background-color: #232444;
                color: #6b6b8a;
                border-color: #2d2e4a;
            }
            #secondaryBtn {
                background-color: transparent;
                border: 1px solid #3f3f6b;
                border-radius: 8px;
                padding: 8px 16px;
                color: #a78bfa;
                font-weight: 600;
                font-size: 13px;
            }
            #secondaryBtn:hover {
                background-color: rgba(167, 139, 250, 0.1);
            }
            #closeBtn {
                background-color: transparent;
                border: none;
                padding: 8px 16px;
                color: #6b6b8a;
                font-size: 13px;
            }
            #closeBtn:hover {
                color: #e0e0e8;
            }
            #iconBtn {
                background-color: transparent;
                border: none;
                font-size: 20px;
                color: #6b6b8a;
            }
            #iconBtn:hover {
                color: #a78bfa;
            }
        """
