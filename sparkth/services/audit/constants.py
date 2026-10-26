"""Constants for reading the audit trail."""

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200

# Rows fetched per round trip while streaming an export, so a multi-year export
# never holds the whole trail in memory.
EXPORT_BATCH_SIZE = 500

# Leading characters that make Excel or Sheets read a CSV cell as a formula.
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
