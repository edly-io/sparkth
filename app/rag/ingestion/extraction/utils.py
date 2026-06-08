"""Shared utilities for the extraction module."""


def render_markdown_table(rows: list[list[str]]) -> str:
    """Render a pre-parsed table as a GitHub-flavoured Markdown table.

    `rows` is a list of rows, each a list of cell strings. The first row
    is treated as the header. Ragged rows are padded with empty cells.
    Returns an empty string if `rows` is empty.
    """
    if not rows:
        return ""

    col_count = max(len(r) for r in rows)

    def pad(row: list[str]) -> list[str]:
        return row + [""] * (col_count - len(row))

    header = pad(rows[0])
    separator = ["---"] * col_count
    body = [pad(r) for r in rows[1:]]

    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(separator) + " |",
        *("| " + " | ".join(r) + " |" for r in body),
    ]
    return "\n".join(lines)
