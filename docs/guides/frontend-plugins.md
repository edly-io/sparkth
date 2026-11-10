# Frontend plugin development

This guide explains how to implement and register a new frontend plugin in the application.
It is the frontend counterpart to the [backend plugin development guide](plugins.md).

The plugin system is designed to be:

- Modular
- Lazy-loaded
- Route-based

> All paths in this guide are relative to the `frontend/` directory.

## Plugin Directory

All plugins live under `plugins/`, and every plugin keeps its code in the same layout:

```
plugins/<pluginname>/
  src/
    index.ts        # the plugin's single entry point
    pages/          # its pages
    client.ts       # its backend API calls
    analytics.ts    # its analytics fetch and chart helpers
    components/
      layout/       # the shell that arranges a page's regions
      ui/           # the regions and everything in them, grouped by feature
    hooks/
    slots/          # what it contributes to slots (icons.ts, settings.ts, ...) and any slot it owns
    i18n/           # its message catalogs and their type
    types.ts
    constants.ts    # its plugin name
  lib/
    index.ts        # its public surface: the only part another plugin may import
  tests/            # its unit tests, mirroring src/, and its Playwright specs in tests/e2e/
```

A page decides what it shows. `components/layout/` holds only the shell that arranges a page's regions. The regions
themselves (a header, a side column or panel, a list) and everything in them go in `components/ui/`, grouped by
feature, even when one fills the whole page.

A plugin creates only the folders it needs: one with no page has just `src/index.ts`, `src/constants.ts` and
`src/slots/`, and only a plugin that offers something to other plugins has a `lib/`.

## 1. Defining a new plugin

Create a new folder named after the backend plugin's package, so `sparkth/plugins/<pluginname>/` and
`frontend/plugins/<pluginname>/` hold the two halves of one plugin. Like the package, it is lowercase with
no hyphens (`googledrive`, not `google-drive`):

    plugins/<pluginname>/

**Example:** Google Drive's backend lives in `sparkth/plugins/googledrive/`, so its frontend lives in

    plugins/googledrive/

Declare the plugin's name once, in `src/constants.ts`, as the name its backend plugin declares, and use the constant
wherever the plugin names itself: its definition, its slot entries and links to its own page. Translation
namespaces stay written out (`useTranslations("exampleplugin")`), because the catalog check reads them as plain
strings.

```ts
// plugins/exampleplugin/src/constants.ts
export const EXAMPLEPLUGIN_PLUGIN_NAME = "exampleplugin";
```

## 2. Create the Plugin UI Component

Inside the new plugin directory, create a React component that represents the plugin’s UI.

**File**

    plugins/<pluginname>/src/pages/<PluginName>.tsx

**Example:**

```ts
"use client";

export default function ExamplePlugin() {
  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold">Example Plugin</h1>
      {/* Plugin UI goes here */}
    </div>
  );
}

```

**Notes**

- Must be a client component
- Reads its own state and config with `usePlugin` from `@/lib/plugins/context`
- This component is lazy-loaded
- Takes shared UI components from `@/lib/components/ui/<Name>`, for example
  `import { Button } from "@/lib/components/ui/Button";`. Core UI lives in `@/core`,
  and `make lint.frontend` rejects any plugin import from it.
- Reads the signed-in user and their token with `useAuth` from `@/lib/auth/hooks`.
- Links to another plugin's page with `pluginPath("<pluginname>")` from `@/lib/plugins/routes`, never by writing the
  `/dashboard/<pluginname>` route out.

## 3. Define the Plugin (index.ts)

Each plugin with a page must export a `PluginDefinition` from its own `src/index.ts`, named after the plugin
(`compose`, `pxc`, `exampleplugin`).

**Example Plugin Structure**

```
plugins/
 └─ exampleplugin/
    └─ src/
       ├─ index.ts
       └─ pages/
          └─ ExamplePlugin.tsx
```

**File**

    plugins/<pluginname>/src/index.ts

**Example**

```ts
import { PluginDefinition } from "@/lib/plugins/types";
import { EXAMPLEPLUGIN_PLUGIN_NAME } from "@/plugins/exampleplugin/src/constants";

export const exampleplugin: PluginDefinition = {
  name: EXAMPLEPLUGIN_PLUGIN_NAME,
  loadComponent: () => import("@/plugins/exampleplugin/src/pages/ExamplePlugin"),
};
```

**Note**

A `PluginDefinition` holds only what the frontend alone can own:

- `name` – unique plugin identifier, used for its route (`dashboard/<name>`) and its slot entries. It must match
  the backend plugin's declared name (see "Plugin Names" in the
  [backend plugin development guide](plugins.md)), so the UI resolves to the right backend plugin
- `loadComponent` – lazy-loaded UI component

The display name, description, icon, and sidebar entry are **declared by the
backend plugin** through the frontend metadata hooks (`DISPLAY_INFO`,
`SIDEBAR_ENTRIES`, `FRONTEND_APPS`, see the backend guide) and arrive on the
user-plugins API response (`display`, `sidebar`, `has_frontend` on
`UserPluginState`). The frontend renders what the backend declares; there is no
frontend-side copy to keep in sync.

`UserPluginState` is the generated `UserPluginResponse` schema
(`Schema<"UserPluginResponse">`), not a hand-written mirror of it, so the shape
cannot drift from the API. One consequence for settings UIs: `config` values are
typed `unknown`, because the backend stores config as JSONB and a field declared
as a string can still arrive as an array or a number. Narrow at the read site.

Icons cross the wire as names, such as a [lucide](https://lucide.dev/icons/) icon name or a brand name. Each plugin
sets the component for every icon name its backend declares in the `PLUGIN_ICONS` slot (see
[Slots](#slots-optional)), from its `src/slots/icons.ts`, which its `src/index.ts` imports. A name is looked up
only among the icons of the plugin that declares it, so two plugins can both declare `plus`. Core keeps no icon map
of its own, so an icon name its plugin did not set renders without an icon, and the resolver logs a `console.warn`
outside production to surface the gap:

```ts
// plugins/exampleplugin/src/slots/icons.ts
import { Plus } from "lucide-react";
import { PLUGIN_ICONS } from "@/lib/icons/slots";
import { EXAMPLEPLUGIN_PLUGIN_NAME } from "@/plugins/exampleplugin/src/constants";

PLUGIN_ICONS.set(EXAMPLEPLUGIN_PLUGIN_NAME, [{ name: "plus", component: Plus }]);
```

For more details, see the `PluginDefinition` type in
[`frontend/core/plugins/types.ts`](https://github.com/edly-io/sparkth/blob/main/frontend/core/plugins/types.ts).

## 4. Register the Plugin

Import the plugin's `src/index.ts` in `app/plugins.ts`, once, and register its `PluginDefinition` with the plugin
registry. Importing the `src/index.ts` also runs any slot files it imports, such as `src/slots/settings.ts`.

**File**

    app/plugins.ts

```ts
import { registerPlugin } from "@/core/plugins/registry";
import { compose } from "@/plugins/compose/src"; // already existing
import { exampleplugin } from "@/plugins/exampleplugin/src";

registerPlugin(compose); // already existing
registerPlugin(exampleplugin);
```

`app/LocaleProvider.tsx` and the dashboard layout import this module, so the plugins are
registered on every page before their catalogs load.

> ⚠️ If a plugin is not imported and registered here, it will not load, not render, and not appear in the sidebar.

## 5. Regenerate the Plugin Route List

Each plugin is rendered under:

    dashboard/<pluginName>

The static routes are **generated from the backend declarations**, not
hand-maintained: `generateStaticParams` in
`app/dashboard/[pluginName]/page.tsx` reads `FRONTEND_PLUGIN_NAMES` from
`lib/plugins/generated.ts`, which lists every backend plugin that registered
the `FRONTEND_APPS` hook. The same file lists, as `PLUGIN_ICON_NAMES`, the icon
names each plugin declares in `DISPLAY_INFO` and `SIDEBAR_ENTRIES`. After
declaring (or removing) a frontend app, or changing a declared icon, on the
backend plugin, regenerate the file:

```bash
make frontend.build.plugins
```

**Notes**

- Do not edit `lib/plugins/generated.ts` by hand. The dump script is its sole
  formatter, so the file is listed in `.oxfmtrc.json` `ignorePatterns` (as
  `lib/api/generated.ts` already is) — otherwise `make format` would rewrite it
  and break the byte-exact backend gate
- To inspect the dump without touching the committed file, run the script with
  no arguments and it prints to stdout:
  `uv run python scripts/dump_frontend_plugins.py`. The make target passes
  `-o frontend/lib/plugins/generated.ts`, which writes atomically, so a failed
  dump leaves the committed file intact
- Tests on both tiers fail when the committed file drifts from the backend
  declarations (`tests/core/test_dump_frontend_plugins.py`), when the
  frontend registry does not match it, or when a plugin sets no component for
  an icon name its backend declares (`frontend/tests/app/plugins.test.ts`)
- `PluginPageClient` handles loading the correct plugin dynamically

## Translations (Optional)

A plugin owns its message catalogs, mirroring the backend rule: the core
`messages/*.json` files carry no plugin namespace, and a plugin with
user-facing strings ships its own catalogs under its directory, scoped to a
single top-level namespace equal to the plugin name.

**1. Create the catalogs**

    plugins/exampleplugin/src/i18n/en.json
    plugins/exampleplugin/src/i18n/es.json
    plugins/exampleplugin/src/i18n/fr.json

```json
{
  "exampleplugin": {
    "greeting": "Hello from the example plugin"
  }
}
```

Every locale in `lib/i18n/config.ts` needs a file, all carrying the same keys.

**2. Declare the loader on the plugin definition**

```ts
import type { Locale } from "@/lib/i18n/config";

const messageCatalogs: Record<Locale, () => Promise<{ default: Record<string, unknown> }>> = {
  en: () => import("@/plugins/exampleplugin/src/i18n/en.json"),
  es: () => import("@/plugins/exampleplugin/src/i18n/es.json"),
  fr: () => import("@/plugins/exampleplugin/src/i18n/fr.json"),
};

export const exampleplugin: PluginDefinition = {
  name: EXAMPLEPLUGIN_PLUGIN_NAME,
  loadComponent: () => import("@/plugins/exampleplugin/src/pages/ExamplePlugin"),
  loadMessages: (locale) => messageCatalogs[locale]().then((catalog) => catalog.default),
};
```

`loadMessages` in `core/i18n/messages.ts` merges every registered plugin's
catalog into the core one at load time; a catalog that fails to load falls
back to the plugin's English one.

**3. Bind the types**

Add a `src/i18n/messages.d.ts` to the plugin that extends the `PluginMessages`
interface in `lib/i18n/messages.ts` with the plugin's English catalog.
TypeScript merges every plugin's declaration into that interface, so unknown
keys fail the typecheck, and core names no plugin:

```ts
// plugins/exampleplugin/src/i18n/messages.d.ts
import type catalog from "@/plugins/exampleplugin/src/i18n/en.json";

type Catalog = typeof catalog;

declare module "@/lib/i18n/messages" {
  interface PluginMessages extends Catalog {}
}
```

Removing the plugin's directory removes its declaration with it.

**4. Use the namespace in components**

```tsx
const t = useTranslations("exampleplugin");

<p>{t("greeting")}</p>
```

Plugin components use only their own namespace, never a core one. The catalog
drift guard (`make test.frontend.i18n`) picks the new `src/i18n/` directory up
automatically and checks it against the plugin's own `src/`, and
`frontend/tests/core/i18n/messages.test.ts` enforces the namespace containment.
In component tests, pass the plugin catalog to the intl helper:
`renderWithIntl(<ExamplePlugin />, exampleEn)`. See the
[translations guide](translations.md#plugin-catalogs) for the full picture.

## Slots (Optional)

A plugin contributes to a core screen, or to another plugin, through a **slot**. A slot is the frontend counterpart
of a backend hook, such as the one behind [Compose agents](plugins.md#compose-agents). It is called a slot
so it is not confused with a React hook.

A slot keeps each plugin's items under the plugin's name. The code that reads the slot decides which plugins'
items to show, for example only the plugins the user has turned on. A slot core reads is defined in `lib`, the way
backend hooks are defined in `sparkth/lib/`, so core and plugins import it from the same path. A slot one plugin
reads belongs to that plugin: it declares the slot in its own `src/slots/` and exports it from its `lib/`, and other
plugins import it from that `lib/` only, as Compose's [attachment sources](#compose-attachment-sources) are.

A file in `src/slots/` usually contributes to a slot owned elsewhere. A file there that declares a slot the plugin owns
says so in its opening comment, so the two kinds are told apart at a glance: Compose's `src/slots/attachments.ts`
declares its attachment slot, while Google Drive's file of the same name contributes a source to it.

**1. Declare the slot** with the type of item it holds: a slot core reads in `lib/<area>/slots.ts`, a slot a
plugin owns in its `src/slots/`, exported from its `lib/`:

```ts
import type { ComponentType } from "react";
import type { Slot } from "@/lib/slots";

export interface ExampleSection {
  title: string;
  loadComponent: () => Promise<{ default: ComponentType }>;
}

export const EXAMPLE_SECTIONS: Slot<ExampleSection> = new Map();
```

**2. Set the plugin's items** from a file of the plugin's own, named for what it contributes, all in one call under
the plugin's name. Setting them again replaces them, so the dev server's hot reload, which runs the file again, adds
nothing twice:

```ts
// plugins/exampleplugin/src/slots/sections.ts
import { EXAMPLE_SECTIONS } from "@/lib/example/slots";
import { EXAMPLEPLUGIN_PLUGIN_NAME } from "@/plugins/exampleplugin/src/constants";

EXAMPLE_SECTIONS.set(EXAMPLEPLUGIN_PLUGIN_NAME, [
  {
    title: "Example",
    loadComponent: () => import("@/plugins/exampleplugin/src/components/ui/ExampleSection"),
  },
]);
```

A file runs only when something imports it, so the plugin's `src/index.ts` imports it, and the file runs when
`app/plugins.ts` imports the plugin:

```ts
// plugins/exampleplugin/src/index.ts
import "@/plugins/exampleplugin/src/slots/sections";
```

**3. Core reads the slot** where its items are rendered. `slotItems` returns each item with the plugin that set
it, ordered by plugin name, and leaves the filtering to the reader:

```tsx
// core/components/example/ExampleSections.tsx
import { usePluginContext } from "@/core/plugins/context";
import { EXAMPLE_SECTIONS } from "@/lib/example/slots";
import { slotItems } from "@/lib/slots";

export function ExampleSections() {
  const { isPluginEnabled } = usePluginContext();
  const sections = slotItems(EXAMPLE_SECTIONS).filter(([plugin]) => isPluginEnabled(plugin));

  return (
    <ul>
      {sections.map(([plugin, section]) => (
        <li key={`${plugin}:${section.title}`}>{section.title}</li>
      ))}
    </ul>
  );
}
```

### Compose attachment sources

Compose's attach menu lists one entry for each source plugins set in its `ATTACHMENT_SOURCES` slot, which Compose
exports from its `lib/` (`@/plugins/compose/lib`), while the plugin that set it is turned on. Choosing an entry
loads the source's picker, which Compose passes the documents already attached as `selected`. The picker hands back
the documents the user picked through `onSelect`, and Compose attaches them in place of every document attached
earlier, from any source; text attachments stay. A plugin sets its source from its own `src/slots/attachments.ts`,
as Google Drive does:

```ts
// plugins/exampleplugin/src/slots/attachments.ts
import { ATTACHMENT_SOURCES } from "@/plugins/compose/lib";
import ExampleIcon from "@/plugins/exampleplugin/src/components/ui/ExampleIcon";
import { EXAMPLEPLUGIN_PLUGIN_NAME } from "@/plugins/exampleplugin/src/constants";

ATTACHMENT_SOURCES.set(EXAMPLEPLUGIN_PLUGIN_NAME, [
  {
    label: "Pick from Example",
    icon: ExampleIcon,
    loadPicker: () => import("@/plugins/exampleplugin/src/components/ui/AttachmentPicker"),
  },
]);
```

The plugin's `src/index.ts` imports that file, or the source is never set:

```ts
// plugins/exampleplugin/src/index.ts
import "@/plugins/exampleplugin/src/slots/attachments";
```

The picker is the module's default export. It gets the attached documents and two callbacks, and finds each one
among its files by `documentId`, so it can show them selected when it opens again:

```tsx
// plugins/exampleplugin/src/components/ui/AttachmentPicker.tsx
import type { AttachmentPickerProps } from "@/plugins/compose/lib";

export default function AttachmentPicker({ selected, onSelect, onClose }: AttachmentPickerProps) {
  // Show the source's files with `selected` ticked. On confirm, hand back every picked document:
  // onSelect([{ documentId, name, size }, ...]). On cancel, call onClose().
}
```

## Analytics (Optional)

A plugin that records analytics events keeps their frontend code in `plugins/<pluginname>/src/analytics.ts`: the
fetch for its analytics endpoint, the response types and the helpers its charts need, built on `@/lib/analytics`
(the date type, the bucket sizes and `buildSeries`). The analytics pages under `app/dashboard/analytics/` import it
from there; core's analytics code in `core/analytics/` holds no plugin's code. Compose's `analytics.ts` is an
example.

A plugin's analytics page is listed on the analytics rail by an entry in `app/dashboard/analytics/views.ts` that
names the plugin (`plugin: "<pluginname>"`); the entry shows only while that plugin is installed.

## Settings

The **Settings** page lists the one row each plugin sets in the `SETTINGS_ITEMS` slot
(`@/lib/settings/slots`), in plugin-name order, for every plugin the user-plugins API returns. The page passes each row
its plugin's state and the actions to turn it on or off, and knows nothing about any plugin. A backend plugin whose
frontend part sets no row does not appear on the page.

A row is a `listItem` component and, when the plugin has config, a `loadConfigModal` that loads the modal editing it.
Core ships both: `SettingsListItem` (`@/lib/components/settings/SettingsListItem`) shows the plugin's name,
description and on/off switch, and the config modal (`@/lib/components/settings/ConfigModal`) builds its form from the
config class the backend plugin declares. Set the row from the plugin's `src/slots/settings.ts`, under the backend
plugin's name, and import that file from the plugin's `src/index.ts`
(`import "@/plugins/exampleplugin/src/slots/settings";`):

```ts
// plugins/exampleplugin/src/slots/settings.ts
import { SettingsListItem } from "@/lib/components/settings/SettingsListItem";
import { SETTINGS_ITEMS } from "@/lib/settings/slots";
import { EXAMPLEPLUGIN_PLUGIN_NAME } from "@/plugins/exampleplugin/src/constants";

SETTINGS_ITEMS.set(EXAMPLEPLUGIN_PLUGIN_NAME, {
  listItem: SettingsListItem,
  loadConfigModal: () => import("@/lib/components/settings/ConfigModal"),
});
```

The row shows its configure button only while the plugin's backend config declares fields, so pass the shared modal
even when the config has no fields yet: adding or removing fields on the backend then needs no frontend change.
While the modal loads, the page passes the row `configuring`, and `SettingsListItem` shows a spinner on its configure
button.

A backend plugin with no page still needs a frontend part for its row: its `src/slots/settings.ts` and a
`src/index.ts` that only imports it, with no `PluginDefinition`. `app/plugins.ts` imports that `src/index.ts` like any
other plugin's, as `import "@/plugins/canvas/src";` does for Canvas.

**Field controls.** A backend field picks its control with a `widget` hint (`sparkth/core/plugins/widgets.py`), and a
field with no hint gets a control from its type. Core ships controls for text, URLs, passwords, numbers, text areas,
checkboxes and LLM configs. When a field needs a control core doesn't ship, the plugin ships its own config modal that
passes the control to core's modal under the hint's name. The control receives `ConfigWidgetProps`
(`@/lib/settings/slots`):

```tsx
import PluginConfigModal from "@/lib/components/settings/ConfigModal";
import type { ConfigModalProps } from "@/lib/settings/slots";
import ExamplePicker from "@/plugins/exampleplugin/src/components/ui/ExamplePicker";

const CONTROLS = { "example-picker": ExamplePicker };

export default function ExampleConfigModal(props: ConfigModalProps) {
  return <PluginConfigModal {...props} controls={CONTROLS} />;
}
```

The plugin's row then loads that modal from `src/components/ui/ExampleConfigModal.tsx`. Core's modal renders a
field with the plugin's control for its hint, then with a built-in control, and falls back to a text input.

## Plugin Loading Flow (Summary)

```
plugins/<plugin>
   ↓
PluginDefinition
   ↓
registerPlugin()
   ↓
Plugin registry
   ↓
Sidebar + routing
   ↓
Dynamic import
   ↓
Rendered plugin UI
```

## Troubleshooting

**Plugin not showing?**

- Ensure `app/plugins.ts` imports its `src/index.ts` and registers it

**Plugin page blank?**

- Check `loadComponent` path
- Ensure component is a default export
- Ensure route param matches plugin name
