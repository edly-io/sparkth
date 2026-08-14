# Backend message catalogs

gettext catalogs for the backend's user-facing strings, one directory per
supported language (`es/LC_MESSAGES/messages.po`, ...). The source language
(English) has no catalog: an untranslated or missing message falls back to the
source string.

The workflow lives in the `i18n.*` Make targets (run from the repo root):

| Command | What it does |
|---|---|
| `make i18n.extract` | Scan `sparkth/` for `_()` / `lazy_gettext()` calls into `messages.pot` |
| `make i18n.init -- <lang>` | Create the catalog for a new language from the template |
| `make i18n.update` | Re-extract and merge new/changed strings into every catalog |
| `make i18n.compile` | Compile `.po` catalogs to the `.mo` files loaded at runtime |

`.po` files are source and are committed; `messages.pot` and `.mo` files are
build artifacts and are git-ignored (`make i18n.compile` must run before the
app can serve translations). How to mark strings is documented in
[docs/guides/translations.md](../../docs/guides/translations.md) and in the
`sparkth.lib.i18n` docstrings.
