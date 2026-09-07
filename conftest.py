"""Root conftest.

Registers ``sparkth.lib.testing`` as a pytest plugin so its shared fixtures (and the
generic test environment it sets on import) are available to every test in the
repo — the central ``tests/`` tree and the co-located
``sparkth/plugins/<plugin>/tests/`` trees alike — without each conftest having
to import and re-export them.

A plugin extracted into its own repository registers the same plugin with this
one line in its own conftest.
"""

pytest_plugins = ["sparkth.lib.testing"]

# `xblock/` is a separate Django distribution with its own pyproject.toml and its own test
# suite (run via `uv run --directory xblock pytest`); it depends on XBlock/Django/web-fragments,
# none of which this application's venv installs. Pytest's plain recursion from the repo root
# would otherwise walk into `xblock/tests/` and abort the whole run with a collection error.
collect_ignore = ["xblock"]
