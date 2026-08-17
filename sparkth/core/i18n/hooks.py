"""Hook through which core and plugins contribute translation catalogs."""

from pathlib import Path

from sparkth.lib.hooks import KeyedItemHook

# Each item is a locale directory holding compiled catalogs
# (``<dir>/<lang>/LC_MESSAGES/messages.mo``). Core registers ``sparkth/locale``
# when :mod:`sparkth.core.i18n.translate` imports; a plugin registers its own
# directory from its ``__init__`` so its catalogs travel with it when it moves
# to its own repository. Every registered directory is consulted when a
# message is translated.
LOCALE_DIRS: KeyedItemHook[Path, Path] = KeyedItemHook(key=lambda locale_dir: locale_dir)
