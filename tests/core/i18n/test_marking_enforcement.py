"""Enforce that every user-facing ``HTTPException`` detail is marked for translation.

Every literal (or f-string) ``detail`` handed to ``HTTPException`` is rendered
to the user, so it must be wrapped in ``_()`` from ``sparkth.lib.i18n``; an
f-string can never be marked because ``pybabel extract`` cannot see inside it.
A deliberately untranslated detail (a machine-read code, an operator-facing
configuration error, request-parameter validation) carries an
``# i18n-exempt: <reason>`` comment on one of the call's lines. Values the
sweep cannot analyze statically (variables, dicts, call results) pass.

No maintained linter covers this (ruff's ``INT`` rules only catch misuse
*inside* gettext calls), so the sweep lives here as a conformance test,
mirroring ``babel.cfg``'s extraction ignores (tests, migrations).

This module was generated with LLM (Claude) assistance.
"""

import ast
from collections.abc import Sequence
from pathlib import Path

from babel.messages.extract import DEFAULT_KEYWORDS, extract_from_dir

import sparkth
from sparkth.plugins.chat.prompt import REFUSAL_MESSAGE

EXEMPT_MARKER = "i18n-exempt"
SKIPPED_DIR_NAMES = {"tests", "migrations", "__pycache__"}
SOURCE_ROOT = Path(sparkth.__file__).resolve().parent
CHAT_PLUGIN_DIR = SOURCE_ROOT / "plugins" / "chat"
# Babel's DEFAULT_KEYWORDS already cover gettext/_; lazy_gettext and gettext_noop are the
# extra `-k` flags the Makefile's i18n.extract target adds on top of them. This is that
# same effective set, kept in step so a divergence never guards something extraction doesn't.
EXTRACT_KEYWORDS = DEFAULT_KEYWORDS | {"lazy_gettext": None, "gettext_noop": None}
# Keywords alone aren't enough: real extraction also skips SKIPPED_DIR_NAMES per babel.cfg's
# `[ignore: **/tests/**]` / `[ignore: migrations/**]`. _extraction_directory_filter below
# applies that same skip, so both the markers and the tree scanned stay in step with the
# Makefile's invocation.

_LITERAL_MESSAGE = (
    f"HTTPException detail is an unmarked string literal: wrap it in _() or add `# {EXEMPT_MARKER}: <reason>`"
)
_F_STRING_MESSAGE = (
    'HTTPException detail is an f-string, which pybabel cannot extract: use _("...").format(...) '
    f"or add `# {EXEMPT_MARKER}: <reason>`"
)


def _is_http_exception(func: ast.expr) -> bool:
    if isinstance(func, ast.Name):
        return func.id == "HTTPException"
    if isinstance(func, ast.Attribute):
        return func.attr == "HTTPException"
    return False


def _detail_argument(call: ast.Call) -> ast.expr | None:
    for keyword in call.keywords:
        if keyword.arg == "detail":
            return keyword.value
    # HTTPException(status_code, detail): the second positional argument.
    if len(call.args) >= 2:
        return call.args[1]
    return None


def _is_exempt(call: ast.Call, lines: Sequence[str]) -> bool:
    end_lineno = call.end_lineno if call.end_lineno is not None else call.lineno
    return any(EXEMPT_MARKER in lines[index] for index in range(call.lineno - 1, min(end_lineno, len(lines))))


def check_source(source: str, filename: str = "<string>") -> list[str]:
    """Return one ``filename:line: message`` entry per unmarked detail in ``source``."""
    lines = source.splitlines()
    violations: list[str] = []
    for node in ast.walk(ast.parse(source, filename=filename)):
        if not isinstance(node, ast.Call) or not _is_http_exception(node.func):
            continue
        detail = _detail_argument(node)
        if detail is None or _is_exempt(node, lines):
            continue
        if isinstance(detail, ast.Constant) and isinstance(detail.value, str):
            violations.append(f"{filename}:{detail.lineno}: {_LITERAL_MESSAGE}")
        elif isinstance(detail, ast.JoinedStr):
            violations.append(f"{filename}:{detail.lineno}: {_F_STRING_MESSAGE}")
    return violations


def collect_violations(root: Path) -> list[str]:
    """Check every Python file under ``root``, skipping ``SKIPPED_DIR_NAMES`` directories."""
    violations: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if SKIPPED_DIR_NAMES.intersection(path.parts):
            continue
        violations.extend(check_source(path.read_text(encoding="utf-8"), str(path)))
    return violations


def test_every_http_exception_detail_is_marked_or_exempt() -> None:
    assert collect_violations(SOURCE_ROOT) == []


def test_flags_an_unmarked_literal_detail() -> None:
    source = 'raise HTTPException(status_code=400, detail="Registration is closed")\n'
    [violation] = check_source(source, "api.py")
    assert violation.startswith("api.py:1:")
    assert "_()" in violation


def test_flags_an_f_string_detail() -> None:
    source = 'raise HTTPException(status_code=404, detail=f"Plugin {name} not found")\n'
    [violation] = check_source(source, "api.py")
    assert "f-string" in violation


def test_flags_a_positional_detail_literal() -> None:
    assert len(check_source('raise HTTPException(400, "expired_token")\n')) == 1


def test_flags_attribute_calls_too() -> None:
    assert len(check_source('raise fastapi.HTTPException(status_code=400, detail="Nope")\n')) == 1


def test_accepts_marked_formatted_variable_and_structured_details() -> None:
    assert check_source('raise HTTPException(status_code=400, detail=_("Nope"))\n') == []
    assert check_source('raise HTTPException(status_code=404, detail=_("Role {n}").format(n=n))\n') == []
    assert check_source("raise HTTPException(status_code=502, detail=detail)\n") == []
    assert check_source('raise HTTPException(status_code=403, detail={"code": "email_not_verified"})\n') == []
    assert check_source("raise HTTPException(status_code=500)\n") == []
    assert check_source('raise ValueError("plain message")\n') == []


def test_exempt_marker_suppresses_on_the_call_line_and_inside_a_multiline_call() -> None:
    single = 'raise HTTPException(status_code=400, detail="expired_token")  # i18n-exempt: machine-read code\n'
    assert check_source(single) == []
    multi = (
        "raise HTTPException(\n"
        "    status_code=422,\n"
        '    detail="Invalid cursor format.",  # i18n-exempt: request-parameter validation\n'
        ")\n"
    )
    assert check_source(multi) == []


def test_collect_violations_skips_tests_and_migrations(tmp_path: Path) -> None:
    bad = 'raise HTTPException(status_code=400, detail="Nope")\n'
    (tmp_path / "routes.py").write_text(bad)
    (tmp_path / "migrations").mkdir()
    (tmp_path / "migrations" / "m1.py").write_text(bad)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_routes.py").write_text(bad)

    violations = collect_violations(tmp_path)

    assert len(violations) == 1
    assert "routes.py" in violations[0]


def _extraction_directory_filter(dirpath: str) -> bool:
    """Keep this test's view of the tree identical to ``babel.cfg``'s, so the guard
    cannot be satisfied by a file real extraction never reads."""
    return Path(dirpath).name not in SKIPPED_DIR_NAMES


def test_the_chat_refusal_is_extractable_by_pybabel() -> None:
    """The refusal must reach the catalogs, and only extraction can prove it does.

    ``gettext_noop`` returns its argument unchanged, so deleting the wrapper changes
    nothing observable at runtime: ``gettext`` is content-keyed and keeps translating
    from the catalog entry that already exists. What breaks is extraction — the msgid
    stops being found, the next catalog update marks it obsolete, and the shipped
    translations rot with no test failing. This asserts the extractor's view, which is
    the only view that can see the marking.

    ``REFUSAL_MESSAGE`` is imported rather than duplicated as a literal here so the
    assertion tracks whatever sentence is actually shipped.
    """
    messages = {
        message
        for _filename, _lineno, message, _comments, _context in extract_from_dir(
            CHAT_PLUGIN_DIR, keywords=EXTRACT_KEYWORDS, directory_filter=_extraction_directory_filter
        )
        if isinstance(message, str)
    }
    assert REFUSAL_MESSAGE in messages
