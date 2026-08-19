"""Catalog containment: each catalog carries only its own package's strings.

Core extraction ignores ``sparkth/plugins/`` (see ``babel.cfg``): a plugin that
marks user-facing strings owns the catalogs under its own ``locale/`` directory,
so its translations travel with it when it moves to its own repository. The
committed ``.po`` files record the sources they cover in the ``#:`` location
comments written by ``make i18n.extract``; these tests fail when an extraction
run leaks strings across that boundary, when a plugin marks strings without
owning catalogs, or when a plugin catalog misses a platform language.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[3]
CORE_LOCALE_DIR = REPO_ROOT / "sparkth" / "locale"
PLUGINS_DIR = REPO_ROOT / "sparkth" / "plugins"


def _po_files(locale_dir: Path) -> list[Path]:
    return sorted(locale_dir.glob("*/LC_MESSAGES/*.po"))


def _source_references(po_file: Path) -> list[str]:
    """The source files named by the catalog's ``#:`` location comments."""
    references: list[str] = []
    for line in po_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("#:"):
            references.extend(location.rsplit(":", 1)[0] for location in line[2:].split())
    return references


def _plugin_dirs() -> list[Path]:
    return sorted(path for path in PLUGINS_DIR.iterdir() if path.is_dir() and not path.name.startswith("__"))


@pytest.mark.parametrize("po_file", _po_files(CORE_LOCALE_DIR), ids=lambda po: str(po.relative_to(REPO_ROOT)))
def test_core_catalogs_carry_no_plugin_strings(po_file: Path) -> None:
    plugin_references = sorted({ref for ref in _source_references(po_file) if ref.startswith("sparkth/plugins/")})
    assert plugin_references == []


@pytest.mark.parametrize("plugin_dir", _plugin_dirs(), ids=lambda plugin: plugin.name)
def test_a_plugin_marking_strings_owns_catalogs(plugin_dir: Path) -> None:
    sources = [path for path in plugin_dir.rglob("*.py") if "tests" not in path.parts]
    if not any("sparkth.lib.i18n" in source.read_text(encoding="utf-8") for source in sources):
        pytest.skip(f"{plugin_dir.name} marks no strings")
    assert (plugin_dir / "locale").is_dir()


@pytest.mark.parametrize(
    "locale_dir",
    [plugin / "locale" for plugin in _plugin_dirs() if (plugin / "locale").is_dir()],
    ids=lambda locale_dir: locale_dir.parent.name,
)
def test_plugin_catalogs_carry_only_their_own_strings(locale_dir: Path) -> None:
    own_prefix = f"sparkth/plugins/{locale_dir.parent.name}/"
    for po_file in _po_files(locale_dir):
        foreign = sorted({ref for ref in _source_references(po_file) if not ref.startswith(own_prefix)})
        assert foreign == [], f"{po_file.relative_to(REPO_ROOT)} references sources outside the plugin"


@pytest.mark.parametrize(
    "locale_dir",
    [plugin / "locale" for plugin in _plugin_dirs() if (plugin / "locale").is_dir()],
    ids=lambda locale_dir: locale_dir.parent.name,
)
def test_plugin_catalogs_cover_every_core_language(locale_dir: Path) -> None:
    core_languages = {path.name for path in CORE_LOCALE_DIR.iterdir() if path.is_dir()}
    languages = {path.name for path in locale_dir.iterdir() if path.is_dir()}
    assert languages == core_languages
