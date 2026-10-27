"""Render the dev VM's ``.env.local`` from the GitHub ``dev`` environment.

This module was generated with LLM (Claude) assistance.

The deploy workflow passes ``toJSON(secrets)`` and ``toJSON(vars)`` in the
``SECRETS_JSON`` and ``VARS_JSON`` environment variables; the rendered file is
written to stdout as single-quoted ``NAME='value'`` lines, which compose reads
literally (no ``$`` interpolation, no ``#`` comments).

Only entries named ``ENV_<NAME>`` are rendered, as ``<NAME>``. GitHub merges org,
repo and environment entries into both maps, so the prefix is what keeps CI
tokens and other repositories' secrets off the VM.

Rendering fails, naming the offending entries but never their values, when a
name is set as both a secret and a variable, when a value holds a single quote
or a newline (which the quoting cannot carry), or when a required entry is
missing — without the last check the app would silently fall back to the
committed ``.env`` defaults, such as its ``ENCRYPTION_KEY``.

The script runs on the VM's system ``python3``, so it uses only the standard
library.
"""

import json
import os
import sys

PREFIX = "ENV_"
REQUIRED = (
    "SECRET_KEY",
    "ENCRYPTION_KEY",
    "POSTGRES_PASSWORD",
    "DATABASE_URL",
    "ANALYTICS_DATABASE_URL",
    "REDIS_URL",
)


def strip_prefix(entries: dict[str, str]) -> dict[str, str]:
    """Keep only ``ENV_``-prefixed entries, keyed by the name without the prefix."""
    return {name[len(PREFIX) :]: value for name, value in entries.items() if name.startswith(PREFIX)}


def check(secrets: dict[str, str], variables: dict[str, str]) -> None:
    """Raise ``ValueError`` naming every entry the rendered file cannot carry."""
    both = sorted(secrets.keys() & variables.keys())
    if both:
        raise ValueError(f"set as both a secret and a variable: {', '.join(both)}")
    entries = secrets | variables
    missing = [name for name in REQUIRED if not entries.get(name)]
    if missing:
        raise ValueError(f"missing required entries: {', '.join(missing)}")
    unquotable = sorted(name for name, value in entries.items() if "'" in value or "\n" in value)
    if unquotable:
        raise ValueError(f"values contain a single quote or a newline: {', '.join(unquotable)}")


def render(secrets: dict[str, str], variables: dict[str, str]) -> str:
    """Render the ``ENV_``-prefixed secrets and variables as ``.env.local`` contents."""
    secret_entries = strip_prefix(secrets)
    variable_entries = strip_prefix(variables)
    check(secret_entries, variable_entries)
    entries = secret_entries | variable_entries
    return "".join(f"{name}='{entries[name]}'\n" for name in sorted(entries))


def main() -> None:
    """Print the rendered file, or exit non-zero with the reason it cannot be rendered."""
    try:
        contents = render(json.loads(os.environ["SECRETS_JSON"]), json.loads(os.environ["VARS_JSON"]))
    except ValueError as exc:
        sys.exit(f"render_env_local: {exc}")
    sys.stdout.write(contents)


if __name__ == "__main__":
    main()
