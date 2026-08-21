# Translations

The backend translates its user-facing strings (API error details, bot
messages, emails) with gettext; the frontend translates its static UI with
[next-intl](https://next-intl.dev). This guide covers how the locale is
resolved on each side, how to mark a string, and how the catalog workflows
run. The backend public API lives in `sparkth.lib.i18n` (see the
[Python API reference](../reference/lib.md)); the frontend helpers live in
`frontend/lib/i18n/`.

## Two languages, resolved separately

Sparkth resolves two different languages and they are deliberately unrelated. Conflating
them is the single most common mistake when working on this code.

**Interface language** — Sparkth's own text: labels, buttons, API error messages, and any
fixed string the backend authors. It is resolved server-side, from the signed-in user's
stored preference, then the `Accept-Language` header, then `DEFAULT_LANGUAGE`. It is
limited to the languages the platform ships catalogs for, because a translation either
exists or it does not. Everything else in this guide is about this language.

**Generated language** — what the model writes: chat replies, course titles, lesson text,
assessment questions, answer options, feedback, and conversation titles. It is not
resolved from a stored preference or a negotiated header, the way interface language is.
In chat, the prompts instruct the model to write in the language of the user's most recent
message and to switch when the user switches; a conversation title instead follows the
language of the message the conversation opened with, and the MCP course-generation tool
takes an explicit tag from its caller rather than reading one off a message. Either way,
there is no tag to store and no allowlist to check — any language the model handles works.
The one setting that can decide a generated language is `DEFAULT_LANGUAGE`: the MCP tool
falls back to it when its caller omits the tag or sends an unusable one.

The practical consequences worth knowing:

- A user whose interface is English can hold an entire conversation in Japanese and get a
  Japanese course. Neither setting affects the other.
- Nothing on the server records which language a course was generated in. A surface that
  needs the tag as data has to be handed it: the MCP course-generation tool takes it as a
  parameter from its caller, and the Open edX publishing path asks the model for the same
  tag again when it creates a course run, since the model is the only thing that knows
  which language it wrote the course in.
- Internal prompts stay English on purpose: the scope classifier, the retrieval intent
  router and the document search agent reason in English while handling input in any
  language. Nothing they produce is shown to a user.
- Output quality varies by language and Sparkth does not restrict which languages it will
  generate in, so output in a language nobody has reviewed is possible.

The out-of-scope chat refusal is the one string that touches both. When the assistant
model itself judges a request out of scope, it is handed the English source and told to
send it in the conversation's language. A faster check can also catch the request first;
a classification step may run there, but it only decides whether the request is in scope
— the backend writes the refusal sentence itself rather than a model, so that refusal
follows the interface language instead.

## Backend

### How the locale is resolved

Any response rendered at or after authentication resolves its locale in this order:

1. A signed-in user's stored `User.language` preference, when set and still one of the
   supported languages, is bound by `get_current_user` once the user is resolved — the
   first point in the request at which the locale is bound to that preference — and
   replaces whatever the middleware negotiated from the header.
2. The `Accept-Language` header, negotiated by `LocaleMiddleware` against the platform
   allowlist (`SUPPORTED_LANGUAGES`, exposed at `GET /api/v1/languages`). Entries are
   taken in listing order, with anything after a `;` discarded: browsers list languages by
   descending preference, so the order alone carries the preference. Matching is exact and
   case-sensitive, so `en-US` does not match `en`, but a browser sending `en-US,en` still
   lands on `en` through its next entry.
3. When neither of the above offers a supported tag — an anonymous request, an unset or
   no-longer-supported stored preference, or a header offering nothing supported — the
   platform [`DEFAULT_LANGUAGE`](../reference/configuration.md#default_language) applies.

A gate that rejects a request outright, before routing, renders its response without the
authentication dependency ever running — so nothing binds the stored preference on its
behalf. Where such a gate has resolved the user itself, it binds the preference before
rendering (`PluginAccessMiddleware` does). A gate that has no user to bind — one rejecting
a request it never authenticated — follows the negotiated header, or `DEFAULT_LANGUAGE`.

Code that runs outside a request (background tasks, CLI) sees
`DEFAULT_LANGUAGE`, or installs a specific locale with
`sparkth.core.i18n.locale_context` (tests do this too).

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
`_()`) is caught by ruff's `INT` rules. A `gettext_noop`-marked constant has
no runtime effect to check this way — `gettext()` stays content-keyed
whether or not the wrapper is present — so that same file also runs
`pybabel`'s extractor directly and asserts the constant is still among the
extracted messages, the only view where the marking is visible at all.

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
   (a language is added only once a full interface translation for it exists
   and has been reviewed; see the comment there).
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
2. Rendering starts immediately on the bundled core English catalog, so the
   prerendered static-export HTML keeps its content. The provider then loads
   the full catalog for the cookie locale: `frontend/messages/<locale>.json`
   merged with the catalog of every registered plugin that ships one (see
   [plugin catalogs](#plugin-catalogs) below). For a non-default locale it
   also sets `document.documentElement.lang` and re-renders in that language
   once the chunks arrive (a brief English flash is inherent to client-side
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
next-intl's types via the `Messages` type in `frontend/lib/i18n/messages.ts`
(referenced from `frontend/lib/i18n/next-intl.d.ts`).

### Plugin catalogs

A frontend plugin owns its catalogs, mirroring the backend containment rule:
the core `frontend/messages/` files carry no plugin namespace, and a plugin
that has user-facing strings ships `messages/<locale>.json` files in its own
directory, scoped to a single top-level namespace equal to the plugin name.
The plugin declares a `loadMessages` loader on its `PluginDefinition`, and
`loadMessages` in `frontend/lib/i18n/messages.ts` merges every registered
plugin's catalog into the core one at load time (a plugin catalog that fails
to load falls back to that plugin's English catalog). See the
[frontend plugin guide](frontend-plugins.md#translations-optional) for the
step-by-step wiring; the containment is guarded by
`frontend/tests/lib/i18n/messages.test.ts`.

### Catalog drift guard

`make test.frontend.i18n` (part of `make test.frontend`, so it runs in CI)
runs [i18n-check](https://github.com/lingualdev/i18n-check) once per catalog
(`frontend/scripts/i18n-check.mjs`): the core `frontend/messages/` catalog is
checked against the core sources, and each `frontend/plugins/*/messages/`
catalog against that plugin's own sources. Each run fails on keys missing
from any locale file, keys whose ICU placeholders diverge from the source,
catalog entries no component uses, and keys used in code but defined in no
catalog. A plugin opts in simply by having a `messages/` directory; the
script picks it up automatically.

### Testing translated components

Wrap the component in the English catalog with `renderWithIntl` from
`frontend/tests/intl-test-utils.tsx`; assertions against English text keep
working unchanged:

```tsx
import { renderWithIntl } from "../intl-test-utils";

renderWithIntl(<HomeClient />);
expect(screen.getByRole("link", { name: "Get Started" })).toBeInTheDocument();
```

A plugin component test passes the plugin's English catalog as the second
argument, since the helper's default carries only the core catalog:

```tsx
import chatEn from "@/plugins/chat/messages/en.json";

renderWithIntl(<ChatInput ... />, chatEn);
```

### Adding a language

1. Add the tag to `SUPPORTED_LANGUAGES` in `sparkth/core/config.py` (see the
   backend steps above).
2. Add the tag to `locales` in `frontend/lib/i18n/config.ts` and create
   `frontend/messages/<lang>.json` with every key from `en.json`
   (`make test.frontend.i18n` verifies completeness).
