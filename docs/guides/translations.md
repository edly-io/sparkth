# Translations

The backend translates its user-facing strings (API error details, bot
messages, emails) with gettext; the frontend translates its static UI with
[next-intl](https://next-intl.dev). This guide covers how the locale is
resolved on each side, how to mark a string, and how the catalog workflows
run. The backend public API lives in `sparkth.lib.i18n` (see the
[Python API reference](../reference/lib.md)); the frontend helpers live in
`frontend/lib/i18n/`.

## Backend

### How the locale is resolved

Every request runs under a locale seeded by `LocaleMiddleware`:

1. The `Accept-Language` header is negotiated against the platform allowlist
   (`SUPPORTED_LANGUAGES`, exposed at `GET /api/v1/languages`). Entries are
   taken in listing order, with anything after a `;` discarded: browsers list
   languages by descending preference, so the order alone carries the
   preference. Matching is exact and case-sensitive, so `en-US` does not
   match `en`, but a browser sending `en-US,en` still lands on `en` through
   its next entry.
2. When nothing offered is supported (or the header is absent), the platform
   [`DEFAULT_LANGUAGE`](../reference/configuration.md#default_language)
   applies.

Code that runs outside a request (background tasks, CLI) sees
`DEFAULT_LANGUAGE`, or installs a specific locale with
`sparkth.core.i18n.locale_context` (tests do this too).

A signed-in user's stored `User.language` does not take part yet: the
middleware runs before authentication, so it never sees the user row. Binding
that preference over the negotiated header belongs in the authentication
dependency, where the audit actor is bound, and is not wired up.

### Marking strings

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

### Catalog workflow

Translations are looked up across every directory registered on the
`LOCALE_DIRS` hook (`sparkth.lib.i18n`). Core registers `sparkth/locale/` (its
README recaps this table), one directory per language. Each catalog carries
only its own package's strings: core extraction ignores `sparkth/plugins/`
(see `babel.cfg`), and a plugin owns the catalogs under its own `locale/`
directory, registered on `LOCALE_DIRS` from its `__init__` (see the
[plugin guide](plugins.md#translations-optional)), so its translations travel with it
when it moves to its own repository.
`tests/core/i18n/test_catalog_containment.py` enforces the boundary. `.po`
files are committed source; the `.pot` template and compiled `.mo` files are
git-ignored build artifacts.

| Command | What it does |
|---|---|
| `make i18n.extract` | Scan for marked strings into the core and per-plugin `messages.pot` |
| `make i18n.init -- <lang>` | Create the core and per-plugin catalogs for a new language |
| `make i18n.update` | Re-extract and merge changes into every catalog |
| `make i18n.compile` | Compile `.po` to the `.mo` files loaded at runtime |

Every target covers the core catalog and each `sparkth/plugins/*/locale/`
directory that exists, so the day-to-day loop after marking or changing
strings is unchanged wherever the string lives: `make i18n.update`, fill in
the new `msgstr` entries in the affected
`<catalog dir>/<lang>/LC_MESSAGES/messages.po`, then `make i18n.compile`
(required before the app can serve the translations).

The production image compiles the catalogs at build time: the `catalog-builder`
stage in the [`Dockerfile`](https://github.com/edly-io/sparkth/blob/main/Dockerfile) runs `pybabel compile` over the
core and per-plugin catalogs with the lockfile-pinned dev dependencies and
hands `sparkth/` (with the compiled `.mo` files) to the runtime stage. A
deployment that does not use the image must run `make i18n.compile` itself
before starting the server.

### Adding a language

1. Add the BCP 47 tag to `SUPPORTED_LANGUAGES` in `sparkth/core/config.py`
   (a language is added only once a speaker has reviewed generated content in
   it; see the comment there).
2. `make i18n.init -- <lang>`, translate the core and per-plugin catalogs it
   creates, `make i18n.compile`.
3. The `/api/v1/languages` endpoint and `DEFAULT_LANGUAGE` validation pick up
   the new tag automatically.

### Testing translated code

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

## Frontend

The frontend uses [next-intl](https://next-intl.dev) in cookie-based mode:
production is a static export served by FastAPI (`output: "export"` in
`frontend/next.config.ts`), so there is no Next.js server, no middleware, and
no locale URL prefix. The locale is resolved on the client.

### How the locale is resolved

1. `LocaleProvider` (`frontend/app/LocaleProvider.tsx`, mounted at the root of
   the layout) reads the `NEXT_LOCALE` cookie via
   `readLocaleCookie()` (`frontend/lib/i18n/config.ts`). An absent or
   unsupported value falls back to `en`.
2. Rendering starts immediately on the bundled English catalog, so the
   prerendered static-export HTML keeps its content. For a non-default locale
   the provider loads `frontend/messages/<locale>.json`, sets
   `document.documentElement.lang`, and re-renders in that language once the
   catalog chunk arrives (a brief English flash is inherent to client-side
   locale resolution); if the load fails it logs and stays on English.
3. The provider records the locale it actually renders in
   `frontend/lib/i18n/active-locale.ts`. The cookie stores the *preference*;
   the active locale tracks what is on screen, and the two diverge exactly
   when a catalog load fails and the UI stays on English.
4. The API client echoes the active locale as an `Accept-Language` header on
   every request (`localeMiddleware` in `frontend/lib/api/middleware.ts`), so
   backend responses arrive in the language the frontend renders, cookie or
   not. A caller-supplied `Accept-Language` header wins over the default.

The catalog allowlist lives in `locales` in `frontend/lib/i18n/config.ts` and
names the bundled `messages/*.json` files. The user-facing language picker
reads the authoritative platform list from `GET /api/v1/languages`.

### Marking strings

Components read messages with `useTranslations`, one namespace per route or
feature (and one per plugin, so plugin messages stay portable):

```tsx
const t = useTranslations("home");

<p>{t("tagline")}</p>
<h1>{t.rich("title", { brand: (chunks) => <span className="text-primary-500">{chunks}</span> })}</h1>
```

Messages use ICU syntax for interpolation and plurals
(`"lastDays": "last {days} days"`). Keys are written by hand into
`frontend/messages/en.json` first; `es.json` and `fr.json` must carry the same
keys. Unknown keys are a TypeScript error: the catalogs are bound to
next-intl's types in `frontend/lib/i18n/next-intl.d.ts`.

### Catalog drift guard

`make test.frontend.i18n` (part of `make test.frontend`, so it runs in CI)
runs [i18n-check](https://github.com/lingualdev/i18n-check) over
`frontend/messages/`: it fails on keys missing from any locale file, keys
whose ICU placeholders diverge from the source, catalog entries no component
uses, and keys used in code but defined in no catalog.

### Testing translated components

Wrap the component in the English catalog with `renderWithIntl` from
`frontend/tests/intl-test-utils.tsx`; assertions against English text keep
working unchanged:

```tsx
import { renderWithIntl } from "../intl-test-utils";

renderWithIntl(<HomeClient />);
expect(screen.getByRole("link", { name: "Get Started" })).toBeInTheDocument();
```

### Adding a language

1. Add the tag to `SUPPORTED_LANGUAGES` in `sparkth/core/config.py` (see the
   backend steps above).
2. Add the tag to `locales` in `frontend/lib/i18n/config.ts` and create
   `frontend/messages/<lang>.json` with every key from `en.json`
   (`make test.frontend.i18n` verifies completeness).
