"""Slack TA Bot plugin for Sparkth."""

from pathlib import Path

import sparkth.plugins.slack.audit  # noqa: F401
from sparkth.lib.i18n import LOCALE_DIRS

LOCALE_DIRS.add_item(Path(__file__).parent / "locale")
