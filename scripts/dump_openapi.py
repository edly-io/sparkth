"""Dump the full OpenAPI schema to stdout, offline.

Relies on assemble_app() registering every route (core + plugins) at import
time with no DB, server, or event loop. Output is sorted and indented so the
generated frontend types are diff-stable.
"""

import json
import logging
import sys

# Redirect all log output to stderr before importing app modules so that the
# only thing written to stdout is the JSON schema. app.main calls
# configure_logging() at import time, which uses logging.basicConfig; basicConfig
# is a no-op when handlers are already attached, so adding a stderr handler
# here pre-empts the stdout handler that configure_logging would otherwise add.
logging.basicConfig(stream=sys.stderr)

from app.main import assemble_app  # noqa: E402


def main() -> None:
    schema = assemble_app().openapi()
    json.dump(schema, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
