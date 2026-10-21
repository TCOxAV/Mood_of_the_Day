"""First-run setup wizard.

Shown when no profile exists. Collects:
- Preferred name
- OpenAI API key (optional)
- Gemini API key (optional)
- Personality/interests (multiline)
- Preferred tone and themes

Uses a stacked-page layout (QStackedWidget) for a clean wizard feel.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from mood.learning.profile import UserProfile
from mood.storage.config import is_keyring_available, store_api_key

class SetupWizard(QWidget):
    """Multi-page first-run setup wizard."""

    setup_complete = Signal()

    def __init__(self, profile: UserProfile, parent=None) -> None:
        super().__init__(parent)
        self._profile = profile
        self.setWindowTitle("Mood of the Day — Setup")
        self.setMinimumSize(560, 480)
        self.setStyleSheet(self._stylesheet())

        self._stack = QStackedWidget()
        self._build_welcome_page()
        self._build_api_page()
        self._build_profile_page()
        self._build_thanks_page()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

    def _build_welcome_page(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel("👋 Welcome to Mood of the Day")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel(
            "Each morning, you'll see a famous quotation\n"
            "chosen just for you. Let's get you set up!"
        )
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("What should we call you?")
        self._name_input.setMaxLength(100)
        self._name_input.setMinimumHeight(40)

        next_btn = QPushButton("Get Started →")
        next_btn.setObjectName("primaryBtn")
        next_btn.clicked.connect(lambda: self._go_next(1))

        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self._name_input)
        layout.addWidget(next_btn)
        layout.addStretch()

        self._stack.addWidget(page)

    def _build_api_page(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)
        layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel("🔑 API Keys (Optional)")
        title.setObjectName("title")

        info = QLabel(
            "The app works without API keys using cached quotations.\n"
            "Add keys for personalized, AI-curated selections.\n\n"
            "Note: An OpenAI API key requires separate billing at\n"
            "platform.openai.com — a ChatGPT subscription does NOT include API credits."
        )
        info.setObjectName("infoText")
        info.setWordWrap(True)

        if is_keyring_available():
            storage_info = QLabel("🔒 Keys will be stored in your system keyring.")
        else:
            storage_info = QLabel(
                "⚠ No system keyring found. Keys will be stored in a\n"
                "local file with restricted permissions."
            )
        storage_info.setObjectName("storageInfo")

        openai_label = QLabel("OpenAI API Key:")
        self._openai_key_input = QLineEdit()
        self._openai_key_input.setPlaceholderText("sk-...")
        self._openai_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._openai_key_input.setMinimumHeight(36)

        gemini_label = QLabel("Gemini API Key:")
        self._gemini_key_input = QLineEdit()
        self._gemini_key_input.setPlaceholderText("AIza...")
        self._gemini_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._gemini_key_input.setMinimumHeight(36)

        btn_row = QHBoxLayout()
        back_btn = QPushButton("← Back")
        back_btn.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        next_btn = QPushButton("Next →")
        next_btn.setObjectName("primaryBtn")
        next_btn.clicked.connect(lambda: self._go_next(2))
        btn_row.addWidget(back_btn)
        btn_row.addStretch()
        btn_row.addWidget(next_btn)

        layout.addWidget(title)
        layout.addWidget(info)
        layout.addWidget(storage_info)
        layout.addSpacing(10)
        layout.addWidget(openai_label)
        layout.addWidget(self._openai_key_input)
        layout.addWidget(gemini_label)
        layout.addWidget(self._gemini_key_input)
        layout.addStretch()
        layout.addLayout(btn_row)

        self._stack.addWidget(page)

    def _build_profile_page(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)
        layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel("✨ Tell Us About You")
        title.setObjectName("title")

        personality_label = QLabel("Your personality and interests:")
        self._personality_input = QPlainTextEdit()
        self._personality_input.setPlaceholderText(
            "e.g., I'm a computer science student who loves philosophy,\n"
            "coding, martial arts, and classic literature. I'm curious\n"
            "about everything and enjoy deep conversations."
        )
        self._personality_input.setMaximumHeight(120)

        tone_label = QLabel("Preferred tone for commentary:")
        self._tone_input = QLineEdit()
        self._tone_input.setPlaceholderText(
            "e.g., warm and thoughtful, witty, philosophical, casual"
        )
        self._tone_input.setMinimumHeight(36)

        themes_label = QLabel("Themes you enjoy (comma-separated):")
        self._themes_input = QLineEdit()
        self._themes_input.setPlaceholderText(
            "e.g., stoicism, courage, creativity, science, discipline"
        )
        self._themes_input.setMinimumHeight(36)

        btn_row = QHBoxLayout()
        back_btn = QPushButton("← Back")
        back_btn.clicked.connect(lambda: self._stack.setCurrentIndex(1))
        finish_btn = QPushButton("Finish Setup ✓")
        finish_btn.setObjectName("primaryBtn")
        finish_btn.clicked.connect(self._finish)
        btn_row.addWidget(back_btn)
        btn_row.addStretch()
        btn_row.addWidget(finish_btn)

        layout.addWidget(title)
        layout.addWidget(personality_label)
        layout.addWidget(self._personality_input)
        layout.addWidget(tone_label)
        layout.addWidget(self._tone_input)
        layout.addWidget(themes_label)
        layout.addWidget(self._themes_input)
        layout.addStretch()
        layout.addLayout(btn_row)

        self._stack.addWidget(page)

    def _build_thanks_page(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)

        self._thanks_title = QLabel("🎉 You're All Set!")
        self._thanks_title.setObjectName("title")
        self._thanks_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._thanks_msg = QLabel("")
        self._thanks_msg.setObjectName("subtitle")
        self._thanks_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thanks_msg.setWordWrap(True)

        close_btn = QPushButton("Show My Quote →")
        close_btn.setObjectName("primaryBtn")
        close_btn.clicked.connect(self._on_complete)

        layout.addStretch()
        layout.addWidget(self._thanks_title)
        layout.addWidget(self._thanks_msg)
        layout.addWidget(close_btn)
        layout.addStretch()

        self._stack.addWidget(page)

    def _go_next(self, page_index: int) -> None:
        self._stack.setCurrentIndex(page_index)

    def _finish(self) -> None:
        """Save all collected data and show the thank-you page."""
        name = self._name_input.text().strip() or "Friend"
        self._profile.name = name

        openai_key = self._openai_key_input.text().strip()
        if openai_key:
            store_api_key("openai", openai_key)

        gemini_key = self._gemini_key_input.text().strip()
        if gemini_key:
            store_api_key("gemini", gemini_key)

        self._profile.personality = self._personality_input.toPlainText().strip()
        self._profile.preferred_tone = self._tone_input.text().strip()

        themes_raw = self._themes_input.text().strip()
        if themes_raw:
            themes = [t.strip() for t in themes_raw.split(",") if t.strip()]
            self._profile.preferred_themes = themes

        self._profile.save()

        self._thanks_msg.setText(
            f"Thanks, {name}! Your preferences have been saved.\n\n"
            "Mood of the Day will now show you a personalized\n"
            "quotation each time you log in."
        )
        self._stack.setCurrentIndex(3)

    def _on_complete(self) -> None:
        self.setup_complete.emit()
        self.close()

    @staticmethod
    def _stylesheet() -> str:
        return """
            QWidget {
                background-color: #1a1b2e;
                color: #e0e0e8;
                font-family: 'Inter', 'Segoe UI', sans-serif;
                font-size: 14px;
            }
            #title {
                font-size: 24px;
                font-weight: 700;
                color: #a78bfa;
            }
            #subtitle {
                font-size: 15px;
                color: #9ca3af;
                line-height: 1.5;
            }
            #infoText {
                font-size: 13px;
                color: #9ca3af;
                line-height: 1.4;
            }
            #storageInfo {
                font-size: 12px;
                color: #6ee7b7;
                padding: 8px 12px;
                background-color: rgba(110, 231, 183, 0.08);
                border-radius: 6px;
            }
            QLineEdit, QPlainTextEdit {
                background-color: #252640;
                border: 1px solid #3f3f6b;
                border-radius: 8px;
                padding: 8px 12px;
                color: #e0e0e8;
                font-size: 14px;
            }
            QLineEdit:focus, QPlainTextEdit:focus {
                border-color: #a78bfa;
            }
            QPushButton {
                background-color: #2d2e4a;
                border: 1px solid #3f3f6b;
                border-radius: 8px;
                padding: 10px 24px;
                color: #c4c4d4;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #3a3b5c;
                border-color: #a78bfa;
            }
            #primaryBtn {
                background-color: #7c3aed;
                border: none;
                color: white;
            }
            #primaryBtn:hover {
                background-color: #6d28d9;
            }
            QLabel {
                font-size: 14px;
            }
        """
