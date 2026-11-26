"""RAG plugin for Sparkth: finds what Compose's steps need in the author's attached documents."""

from pathlib import Path

from sparkth.lib.i18n import LOCALE_DIRS

LOCALE_DIRS.add_item(Path(__file__).parent / "locale")
