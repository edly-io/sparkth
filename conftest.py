"""Root conftest.

Registers ``sparkth.testing`` as a pytest plugin so its shared fixtures (and the
generic test environment it sets on import) are available to every test in the
repo — the central ``tests/`` tree and the co-located
``app/core_plugins/<plugin>/tests/`` trees alike — without each conftest having
to import and re-export them.

A plugin extracted into its own repository registers the same plugin with this
one line in its own conftest.
"""

pytest_plugins = ["sparkth.testing"]
