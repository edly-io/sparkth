"""Hook through which core and plugins contribute analytics Overview figures."""

from sparkth.core.analytics.types import SummaryFigure
from sparkth.lib.hooks import KeyedItemHook

# Keyed by figure key. Core seeds its figures when :mod:`sparkth.core.analytics.reads`
# imports; plugins add theirs with ``register_summary_figure`` (``sparkth.lib.analytics``).
SUMMARY_FIGURES: KeyedItemHook[str, SummaryFigure] = KeyedItemHook(key=lambda figure: figure.key)
