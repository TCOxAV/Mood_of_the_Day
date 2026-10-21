"""Application entry point — wires all components together.

Flow:
1. Initialize paths, logging, library, cache, and profile.
2. If first run → show setup wizard → then show popup.
3. If returning user → show popup immediately with cached data.
4. In the background, fill missing cache entries if a provider is up.

Run with: python -m mood.main
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Optional

from PySide6.QtCore import QTimer, Slot
from PySide6.QtWidgets import QApplication

from mood.learning.feedback import FeedbackProcessor
from mood.learning.manager import LearningManager
from mood.learning.profile import UserProfile
from mood.popup import QuotePopup
from mood.providers.base import BaseProvider
from mood.providers.gemini_provider import GeminiProvider
from mood.providers.openai_provider import OpenAIProvider
from mood.quotes.library import QuoteLibrary
from mood.quotes.selector import QuoteSelector
from mood.settings import SettingsDialog
from mood.setup import SetupWizard
from mood.storage.cache import DailyCache
from mood.storage.config import get_api_key
from mood.storage.paths import ensure_dirs

logger = logging.getLogger(__name__)

class MoodApp:
    """Top-level application controller.

    Owns all the major components and coordinates between
    the UI and the backend services.
    """

    def __init__(self) -> None:
        self._profile = UserProfile()
        self._cache = DailyCache()
        self._library = QuoteLibrary()
        self._feedback: Optional[FeedbackProcessor] = None
        self._selector: Optional[QuoteSelector] = None
        self._learning: Optional[LearningManager] = None
        self._popup: Optional[QuotePopup] = None
        self._settings: Optional[SettingsDialog] = None
        self._setup: Optional[SetupWizard] = None

    def _get_selection_provider(self) -> Optional[BaseProvider]:
        """Return the best available provider for quote selection.

        Prefers OpenAI; falls back to Gemini.
        """
        openai = OpenAIProvider()
        if openai.is_configured():
            return openai
        gemini = GeminiProvider()
        if gemini.is_configured():
            return gemini
        return None

    def _get_learning_provider(self) -> Optional[BaseProvider]:
        """Return the best available provider for profile learning.

        Prefers Gemini; falls back to OpenAI.
        """
        gemini = GeminiProvider()
        if gemini.is_configured():
            return gemini
        openai = OpenAIProvider()
        if openai.is_configured():
            return openai
        return None

    def initialize(self) -> None:
        """Load all data and set up the backend."""
        ensure_dirs()
        self._library.load()
        self._cache.load()
        self._cache.prune()
        self._profile.load()

        selection_provider = self._get_selection_provider()
        learning_provider = self._get_learning_provider()

        self._selector = QuoteSelector(
            library=self._library,
            cache=self._cache,
            profile=self._profile,
            selection_provider=selection_provider,
        )
        self._feedback = FeedbackProcessor(self._profile)
        self._learning = LearningManager(
            profile=self._profile,
            learning_provider=learning_provider,
        )

    def show_setup_or_popup(self) -> None:
        """Decide whether to show the setup wizard or the daily popup."""
        if not self._profile.exists:
            self._show_setup()
        else:
            self._show_popup()

    def _show_setup(self) -> None:
        """Show the first-run setup wizard."""
        self._setup = SetupWizard(self._profile)
        self._setup.setup_complete.connect(self._on_setup_complete)
        self._setup.show()

    @Slot()
    def _on_setup_complete(self) -> None:
        """Called when setup finishes — reinitialize and show popup."""
        self.initialize()
        self._show_popup()

    def _show_popup(self) -> None:
        """Show the daily quotation popup."""
        self._popup = QuotePopup()
        self._popup.liked.connect(self._on_like)
        self._popup.disliked.connect(self._on_dislike)
        self._popup.refresh_requested.connect(self._on_refresh)
        self._popup.settings_requested.connect(self._show_settings)

        self._display_today()

        self._popup.show()

        QTimer.singleShot(500, self._background_fill)

    def _display_today(self) -> None:
        """Get today's entry and display it."""
        if not self._selector or not self._popup:
            return

        entry = self._cache.get_today()
        if entry:
            self._popup.display_entry(entry, self._profile.name)
            return

        loop = _get_or_create_event_loop()
        entry = loop.run_until_complete(self._selector.get_today())
        if self._popup:
            self._popup.display_entry(entry, self._profile.name)

    @Slot(str)
    def _on_like(self, quote_id: str) -> None:
        if self._feedback:
            self._feedback.record(quote_id, liked=True)
            if self._feedback.should_trigger_learning():
                self._trigger_learning()

    @Slot(str)
    def _on_dislike(self, quote_id: str) -> None:
        if self._feedback:
            self._feedback.record(quote_id, liked=False)
            if self._feedback.should_trigger_learning():
                self._trigger_learning()

    @Slot()
    def _on_refresh(self) -> None:
        """User clicked refresh — regenerate today's entry."""
        if not self._selector or not self._popup:
            return

        self._popup.set_loading(True)
        loop = _get_or_create_event_loop()
        try:
            entry = loop.run_until_complete(self._selector.regenerate_today())
            if entry and self._popup:
                self._popup.display_entry(entry, self._profile.name)
        except Exception as exc:
            logger.warning("Refresh failed: %s", exc)
        finally:
            if self._popup:
                self._popup.set_loading(False)

    def _show_settings(self) -> None:
        """Open the settings dialog."""
        self._settings = SettingsDialog(self._profile)
        self._settings.profile_updated.connect(self._on_profile_updated)
        self._settings.show()

    @Slot()
    def _on_profile_updated(self) -> None:
        """Re-initialize providers after profile update."""
        self.initialize()

    def _background_fill(self) -> None:
        """Fill missing cache entries in the background."""
        if not self._selector:
            return
        try:
            loop = _get_or_create_event_loop()
            loop.run_until_complete(self._selector.fill_cache())
        except Exception as exc:
            logger.debug("Background cache fill error: %s", exc)

    def _trigger_learning(self) -> None:
        """Run a learning cycle in the background."""
        if not self._learning:
            return
        try:
            loop = _get_or_create_event_loop()
            result = loop.run_until_complete(self._learning.run_learning_cycle())
            if result:
                logger.info("Learning update: %s", result)
        except Exception as exc:
            logger.debug("Learning cycle error: %s", exc)

def _get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """Get the running event loop or create a new one."""
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop

def main() -> None:
    """Application entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Mood of the Day")
    app.setApplicationVersion("0.1.0")

    mood_app = MoodApp()
    mood_app.initialize()
    mood_app.show_setup_or_popup()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
