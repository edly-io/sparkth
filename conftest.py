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

# `third_party_plugins/` holds packages installed into someone else's application rather than
# into Sparkth, each a separate distribution with its own pyproject.toml and test suite. They
# depend on things this application's venv does not install, so pytest's plain recursion from
# the repo root would walk into their tests and abort the whole run with a collection error.
collect_ignore = ["third_party_plugins"]
