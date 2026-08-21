"""
Chat Plugin

Multi-provider LangChain-based chat interface with encrypted API keys,
conversation history, token tracking, and streaming support.
"""

from pathlib import Path

from sparkth.lib.i18n import LOCALE_DIRS

LOCALE_DIRS.add_item(Path(__file__).parent / "locale")
