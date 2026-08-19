"""Built-in Sparkth plugins.

This ``__init__`` also pins the package identity for pytest's prepend import
mode: without it, a plugin's ``tests/conftest.py`` is imported under a package
name rooted at the plugin directory (``googledrive.tests.conftest``), which
re-executes the plugin's ``__init__`` as a second module and breaks its
import-time hook registrations (e.g. ``LOCALE_DIRS``) with duplicate-key
errors.
"""
