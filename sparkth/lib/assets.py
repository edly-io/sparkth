"""Reading a plugin's text assets."""

from pathlib import Path


def read_asset(module_file: str, name: str) -> str:
    """Read ``assets/<name>`` beside ``module_file``, stripped of surrounding whitespace."""
    return (Path(module_file).parent / "assets" / name).read_text(encoding="utf-8").strip()
