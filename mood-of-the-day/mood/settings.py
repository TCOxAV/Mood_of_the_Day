"""Settings dialog — edit profile, manage providers, and reset data.

Accessible from the gear icon on the daily popup.
"""

from __future__ import annotations

import asyncio
import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from mood.learning.profile import UserProfile
from mood.storage.config import delete_api_key, get_api_key, store_api_key, is_keyring_available
from mood.system.autostart import install_autostart, is_autostart_installed, uninstall_autostart

logger = logging.getLogger(__name__)

class SettingsDialog(QWidget):
    """Settings window with tabs for profile, providers, and data."""

    profile_updated = Signal()

    def __init__(self, profile: UserProfile, parent=None) -> None:
        super().__init__(parent)
        self._profile = profile
        self.setWindowTitle("Mood of the Day — Settings")
        self.setMinimumSize(500, 500)
        self.setStyleSheet(self._stylesheet())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        tabs = QTabWidget()
        tabs.addTab(self._build_profile_tab(), "Profile")
        tabs.addTab(self._build_providers_tab(), "Providers")
        tabs.addTab(self._build_data_tab(), "Data")
        layout.addWidget(tabs)

    def _build_profile_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        name_label = QLabel("Your name:")
        self._settings_name = QLineEdit(self._profile.name)
        self._settings_name.setMinimumHeight(36)

        personality_label = QLabel("Personality & interests:")
        self._settings_personality = QPlainTextEdit(self._profile.personality)
        self._settings_personality.setMaximumHeight(100)

        tone_label = QLabel("Preferred tone:")
        self._settings_tone = QLineEdit(self._profile.preferred_tone)
        self._settings_tone.setMinimumHeight(36)

        themes_label = QLabel("Preferred themes (comma-separated):")
        self._settings_themes = QLineEdit(
            ", ".join(self._profile.preferred_themes)
        )
        self._settings_themes.setMinimumHeight(36)

        self._autostart_check = QCheckBox("Start automatically on login")
        self._autostart_check.setChecked(is_autostart_installed())
        self._autostart_check.stateChanged.connect(self._toggle_autostart)

        save_btn = QPushButton("Save Changes")
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self._save_profile)

        layout.addWidget(name_label)
        layout.addWidget(self._settings_name)
        layout.addWidget(personality_label)
        layout.addWidget(self._settings_personality)
        layout.addWidget(tone_label)
        layout.addWidget(self._settings_tone)
        layout.addWidget(themes_label)
        layout.addWidget(self._settings_themes)
        layout.addSpacing(10)
        layout.addWidget(self._autostart_check)
        layout.addStretch()
        layout.addWidget(save_btn)

        return tab

    def _build_providers_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)

        if is_keyring_available():
            info = QLabel("🔒 Keys are stored in your system keyring.")
        else:
            info = QLabel("⚠ Keys stored in a local file (no keyring found).")
        info.setObjectName("storageInfo")
        layout.addWidget(info)

        openai_group = QGroupBox("OpenAI")
        og_layout = QVBoxLayout(openai_group)
        self._openai_key_edit = QLineEdit()
        self._openai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._openai_key_edit.setPlaceholderText(
            "Enter key or leave blank to keep existing"
        )
        self._openai_key_edit.setMinimumHeight(36)

        has_openai = bool(get_api_key("openai"))
        self._openai_status = QLabel(
            "✓ Key configured" if has_openai else "✗ Not configured"
        )
        self._openai_status.setObjectName("statusLabel")

        openai_row = QHBoxLayout()
        test_openai_btn = QPushButton("Test Connection")
        test_openai_btn.setObjectName("secondaryBtn")
        test_openai_btn.clicked.connect(self._test_openai_connection)
        openai_row.addWidget(self._openai_status)
        openai_row.addStretch()
        openai_row.addWidget(test_openai_btn)

        og_layout.addLayout(openai_row)
        og_layout.addWidget(self._openai_key_edit)
        layout.addWidget(openai_group)

        gemini_group = QGroupBox("Google Gemini")
        gg_layout = QVBoxLayout(gemini_group)
        self._gemini_key_edit = QLineEdit()
        self._gemini_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._gemini_key_edit.setPlaceholderText(
            "Enter key or leave blank to keep existing"
        )
        self._gemini_key_edit.setMinimumHeight(36)

        has_gemini = bool(get_api_key("gemini"))
        self._gemini_status = QLabel(
            "✓ Key configured" if has_gemini else "✗ Not configured"
        )
        self._gemini_status.setObjectName("statusLabel")

        gemini_row = QHBoxLayout()
        test_gemini_btn = QPushButton("Test Connection")
        test_gemini_btn.setObjectName("secondaryBtn")
        test_gemini_btn.clicked.connect(self._test_gemini_connection)
        gemini_row.addWidget(self._gemini_status)
        gemini_row.addStretch()
        gemini_row.addWidget(test_gemini_btn)

        gg_layout.addLayout(gemini_row)
        gg_layout.addWidget(self._gemini_key_edit)
        layout.addWidget(gemini_group)

        save_btn = QPushButton("Save Keys")
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self._save_keys)

        layout.addStretch()
        layout.addWidget(save_btn)

        return tab

    def _build_data_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)

        info = QLabel(
            "Manage your local data. These actions only affect\n"
            "data stored on your computer."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        reset_learned_btn = QPushButton("Reset Learned Preferences")
        reset_learned_btn.setToolTip(
            "Clears liked/disliked themes and authors learned from feedback.\n"
            "Your name, personality, and interests are preserved."
        )
        reset_learned_btn.clicked.connect(self._reset_learned)

        clear_cache_btn = QPushButton("Clear Quote Cache")
        clear_cache_btn.setToolTip("Removes cached quotations. New ones will be generated.")
        clear_cache_btn.clicked.connect(self._clear_cache)

        delete_keys_btn = QPushButton("Remove All API Keys")
        delete_keys_btn.setObjectName("dangerBtn")
        delete_keys_btn.clicked.connect(self._delete_keys)

        layout.addWidget(reset_learned_btn)
        layout.addWidget(clear_cache_btn)
        layout.addSpacing(20)
        layout.addWidget(delete_keys_btn)
        layout.addStretch()

        return tab

    def _save_profile(self) -> None:
        self._profile.name = self._settings_name.text().strip()
        self._profile.personality = self._settings_personality.toPlainText().strip()
        self._profile.preferred_tone = self._settings_tone.text().strip()

        themes_raw = self._settings_themes.text().strip()
        if themes_raw:
            self._profile.preferred_themes = [
                t.strip() for t in themes_raw.split(",") if t.strip()
            ]
        else:
            self._profile.preferred_themes = []

        self._profile.save()
        self.profile_updated.emit()
        QMessageBox.information(self, "Saved", "Your profile has been updated.")

    def _save_keys(self) -> None:
        openai_key = self._openai_key_edit.text().strip()
        if openai_key:
            store_api_key("openai", openai_key)
            self._openai_status.setText("✓ Key configured")

        gemini_key = self._gemini_key_edit.text().strip()
        if gemini_key:
            store_api_key("gemini", gemini_key)
            self._gemini_status.setText("✓ Key configured")

        self.profile_updated.emit()
        QMessageBox.information(self, "Saved", "API keys updated.")

    def _test_openai_connection(self) -> None:
        key = self._openai_key_edit.text().strip()
        if key:
            store_api_key("openai", key)
            self._openai_status.setText("✓ Key configured")
        from mood.providers.openai_provider import OpenAIProvider
        provider = OpenAIProvider()
        if not provider.is_configured():
            QMessageBox.warning(
                self, "OpenAI", "Please enter or configure an OpenAI API key first."
            )
            return

        try:
            ok = asyncio.run(provider.test_connection())
            if ok:
                QMessageBox.information(
                    self, "OpenAI Connection", "✓ Connection successful! OpenAI API key is valid."
                )
            else:
                QMessageBox.warning(
                    self, "OpenAI Connection", "✗ Connection failed. Please check your API key and quota."
                )
        except Exception as exc:
            QMessageBox.critical(self, "OpenAI Connection", f"Error testing OpenAI: {exc}")

    def _test_gemini_connection(self) -> None:
        key = self._gemini_key_edit.text().strip()
        if key:
            store_api_key("gemini", key)
            self._gemini_status.setText("✓ Key configured")
        from mood.providers.gemini_provider import GeminiProvider
        provider = GeminiProvider()
        if not provider.is_configured():
            QMessageBox.warning(
                self, "Gemini", "Please enter or configure a Gemini API key first."
            )
            return

        try:
            ok = asyncio.run(provider.test_connection())
            if ok:
                QMessageBox.information(
                    self, "Gemini Connection", "✓ Connection successful! Gemini API key is valid."
                )
            else:
                QMessageBox.warning(
                    self, "Gemini Connection", "✗ Connection failed. Please check your API key and quota."
                )
        except Exception as exc:
            QMessageBox.critical(self, "Gemini Connection", f"Error testing Gemini: {exc}")

    def _reset_learned(self) -> None:
        reply = QMessageBox.question(
            self,
            "Reset Learned Preferences?",
            "This will clear all learned themes and authors.\n"
            "Your name and interests will be kept.\n\nContinue?",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._profile.reset_learned()
            self._profile.save()
            QMessageBox.information(self, "Reset", "Learned preferences cleared.")

    def _clear_cache(self) -> None:
        from mood.storage.cache import DailyCache
        cache = DailyCache()
        cache.clear()
        cache.save()
        QMessageBox.information(self, "Cleared", "Quote cache has been cleared.")

    def _delete_keys(self) -> None:
        reply = QMessageBox.warning(
            self,
            "Remove All API Keys?",
            "This will delete both OpenAI and Gemini API keys.\n"
            "The app will run in offline/fallback mode.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_api_key("openai")
            delete_api_key("gemini")
            self._openai_status.setText("✗ Not configured")
            self._gemini_status.setText("✗ Not configured")
            self.profile_updated.emit()
            QMessageBox.information(self, "Removed", "All API keys deleted.")

    def _toggle_autostart(self, state: int) -> None:
        if state == Qt.CheckState.Checked.value:
            if install_autostart():
                logger.info("Autostart enabled.")
            else:
                QMessageBox.warning(self, "Error", "Failed to enable autostart.")
                self._autostart_check.setChecked(False)
        else:
            uninstall_autostart()
            logger.info("Autostart disabled.")

    @staticmethod
    def _stylesheet() -> str:
        return """
            QWidget {
                background-color: #1a1b2e;
                color: #e0e0e8;
                font-family: 'Inter', 'Segoe UI', sans-serif;
                font-size: 14px;
            }
            QTabWidget::pane {
                border: 1px solid #3f3f6b;
                border-radius: 8px;
                background-color: #1e1f36;
                top: -1px;
            }
            QTabBar::tab {
                background-color: #252640;
                border: 1px solid #3f3f6b;
                border-bottom: none;
                padding: 8px 20px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                color: #9ca3af;
            }
            QTabBar::tab:selected {
                background-color: #1e1f36;
                color: #a78bfa;
            }
            QGroupBox {
                border: 1px solid #3f3f6b;
                border-radius: 8px;
                margin-top: 16px;
                padding: 16px;
                font-weight: 600;
                color: #c4b5fd;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                padding: 0 8px;
            }
            QLineEdit, QPlainTextEdit {
                background-color: #252640;
                border: 1px solid #3f3f6b;
                border-radius: 8px;
                padding: 8px 12px;
                color: #e0e0e8;
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
            #dangerBtn {
                background-color: #7f1d1d;
                border: 1px solid #991b1b;
                color: #fca5a5;
            }
            #dangerBtn:hover {
                background-color: #991b1b;
            }
            #statusLabel {
                font-size: 12px;
                color: #6ee7b7;
            }
            #storageInfo {
                font-size: 12px;
                color: #6ee7b7;
                padding: 8px;
                background-color: rgba(110, 231, 183, 0.08);
                border-radius: 6px;
            }
            QCheckBox {
                spacing: 8px;
                color: #c4c4d4;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
        """
