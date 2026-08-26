# Backend message catalogs (core)

gettext catalogs for core's user-facing strings, one directory per supported
language (`es/LC_MESSAGES/messages.po`, ...). The source language (English)
has no catalog: an untranslated or missing message falls back to the source
string. Plugin strings are not here: each plugin owns the catalogs under its
own `sparkth/plugins/<name>/locale/` directory, registered on the
`LOCALE_DIRS` hook so they travel with the plugin.

The workflow lives in the `i18n.*` Make targets (run from the repo root); each
target covers this directory and every plugin `locale/` directory:

| Command | What it does |
|---|---|
| `make i18n.extract` | Scan for marked strings into the core and per-plugin `messages.pot` |
| `make i18n.init -- <lang>` | Create the catalogs for a new language from the templates |
| `make i18n.update` | Re-extract and merge new/changed strings into every catalog |
| `make i18n.compile` | Compile `.po` catalogs to the `.mo` files loaded at runtime |

`.po` files are source and are committed; `messages.pot` and `.mo` files are
build artifacts and are git-ignored (`make i18n.compile` must run before the
app can serve translations). How to mark strings is documented in
[docs/guides/translations.md](../../docs/guides/translations.md) and in the
`sparkth.lib.i18n` docstrings.
