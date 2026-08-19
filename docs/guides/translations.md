# Translations (backend i18n)

The backend translates its user-facing strings (API error details, bot
messages, emails) with gettext. This guide covers how the locale is resolved,
how to mark a string, and how the catalog workflow runs. The public API lives
in `sparkth.lib.i18n` (see the [Python API reference](../reference/lib.md)).

## How the locale is resolved

Any response rendered at or after authentication resolves its locale in this order:

1. A signed-in user's stored `User.language` preference, when set and still one of the
   supported languages, is bound by `get_current_user` once the user is resolved — the
   first point in the request at which a signed-in user is known — and replaces whatever
   the middleware negotiated from the header.
2. The `Accept-Language` header, negotiated by `LocaleMiddleware` against the platform
   allowlist (`SUPPORTED_LANGUAGES`, exposed at `GET /api/v1/languages`). Entries are
   taken in listing order, with anything after a `;` discarded: browsers list languages by
   descending preference, so the order alone carries the preference. Matching is exact and
   case-sensitive, so `en-US` does not match `en`, but a browser sending `en-US,en` still
   lands on `en` through its next entry.
3. When neither of the above offers a supported tag — an anonymous request, an unset or
   no-longer-supported stored preference, or a header offering nothing supported — the
   platform [`DEFAULT_LANGUAGE`](../reference/configuration.md#default_language) applies.

A response produced by a gate that runs ahead of authentication — rejecting a request
outright before any dependency resolves the caller — has no signed-in user to bind a
stored preference from yet, so it follows the negotiated header (or `DEFAULT_LANGUAGE`)
only.

Code that runs outside a request (background tasks, CLI) sees
`DEFAULT_LANGUAGE`, or installs a specific locale with
`sparkth.core.i18n.locale_context` (tests do this too).

## Marking strings

Import the marking functions from `sparkth.lib.i18n`, never from
`sparkth.core.*`:

```python
from sparkth.lib.i18n import _, lazy_gettext
```

There are four cases:

- **A literal evaluated during a request**: wrap it in `_()` at the point of
  use.

  ```python
  raise HTTPException(status_code=401, detail=_("Incorrect username or password"))
  ```

- **An f-string**: `pybabel extract` cannot see inside f-strings. Convert to
  `str.format` on the translated template:

  ```python
  # before: f"Role not found: {role_name}"
  _("Role not found: {role_name}").format(role_name=role_name)
  ```

- **A module-level constant**: module bodies run at import, before any request
  locale exists. Mark with `lazy_gettext()`, which defers translation until
  the value is rendered, and call `str()` on it at the boundary (response
  serialization, message dispatch):

  ```python
  GREETING_MESSAGE = lazy_gettext("Hello! How can I help you?")
  ...
  await post_message(str(GREETING_MESSAGE))
  ```

- **A constant stored in a plain-`str` field** (a dataclass a response model
  embeds, where a `LazyString` cannot go, e.g. the `DisplayInfo` /
  `SidebarEntry` frontend metadata): mark the literal with `gettext_noop()`,
  which returns it unchanged, and translate the stored value by passing it
  through `gettext()` at the rendering boundary (`UserPluginResponse.for_plugin`
  does this for the frontend metadata):

  ```python
  DISPLAY_INFO.add_item(self, DisplayInfo(gettext_noop("Create Course"), gettext_noop("Build courses with AI")))
  ```

Only user-facing text is marked. Log lines, LLM prompt templates, MCP tool
descriptions, and OpenAPI field descriptions stay English, as do machine-read
error codes (`"expired_token"`), operator-facing configuration errors
("Slack credentials not configured."), and hand-rolled request-parameter
validation messages, which follow the untranslated Pydantic `422`s.

The `HTTPException` slice of this rule is enforced by the suite:
[`tests/core/i18n/test_marking_enforcement.py`](https://github.com/edly-io/sparkth/blob/main/tests/core/i18n/test_marking_enforcement.py)
fails on any literal or f-string `detail` that is neither `_()`-wrapped nor
annotated with an `# i18n-exempt: <reason>` comment on one of the call's
lines. Misuse inside the marking calls themselves (an f-string passed to
`_()`) is caught by ruff's `INT` rules.

## Catalog workflow

Translations are looked up across every directory registered on the
`LOCALE_DIRS` hook (`sparkth.lib.i18n`). Core registers `sparkth/locale/` (its
README recaps this table), one directory per language; a plugin that ships its
own catalogs registers its directory from its `__init__` (see the
[plugin guide](plugins.md#translations-optional)). `.po` files are committed
source; the `.pot` template and compiled `.mo` files are git-ignored build
artifacts.

| Command | What it does |
|---|---|
| `make i18n.extract` | Scan `sparkth/` for marked strings into `messages.pot` |
| `make i18n.init -- <lang>` | Create the catalog for a new language |
| `make i18n.update` | Re-extract and merge changes into every catalog |
| `make i18n.compile` | Compile `.po` to the `.mo` files loaded at runtime |

The day-to-day loop after marking or changing strings: `make i18n.update`,
fill in the new `msgstr` entries in each `sparkth/locale/<lang>/LC_MESSAGES/messages.po`,
then `make i18n.compile` (required before the app can serve the translations).

The production image compiles the catalogs at build time: the `catalog-builder`
stage in the [`Dockerfile`](https://github.com/edly-io/sparkth/blob/main/Dockerfile) runs `pybabel compile` with the
lockfile-pinned dev dependencies and hands only `sparkth/locale` (with the
compiled `.mo` files) to the runtime stage. A deployment that does not use the
image must run `make i18n.compile` itself before starting the server.

## Adding a language

1. Add the BCP 47 tag to `SUPPORTED_LANGUAGES` in `sparkth/core/config.py`
   (a language is added only once a full interface translation for it exists
   and has been reviewed; see the comment there).
2. `make i18n.init -- <lang>`, translate the catalog, `make i18n.compile`.
3. The `/api/v1/languages` endpoint and `DEFAULT_LANGUAGE` validation pick up
   the new tag automatically.

## Testing translated code

The suite detaches the shipped catalog directories for the whole session
(the `shipped_locale_dirs` fixture in `sparkth.lib.testing`), so locally
compiled `.mo` files never leak into tests: every lookup falls back to the
English source string, and assertions against English text keep working. To
assert on an actual translation, inject a catalog with the
`translation_catalog` fixture and render under the target locale, via
`locale_context("<lang>")` or an `Accept-Language` header:

```python
async def test_detail_is_translated(client, translation_catalog):
    translation_catalog("Incorrect username or password", "Usuario o contraseña incorrectos")
    response = await client.post(..., headers={"Accept-Language": "es"})
```
