"""Constants for reading the audit trail."""

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200

# Rows fetched per round trip while streaming an export, so a multi-year export
# never holds the whole trail in memory.
EXPORT_BATCH_SIZE = 500

# Byte-order mark a CSV export starts with, so spreadsheets read it as UTF-8.
CSV_BOM = "\ufeff"

# Leading characters that make Excel or Sheets read a CSV cell as a formula.
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
