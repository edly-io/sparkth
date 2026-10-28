# Frontend plugin development

This guide explains how to implement and register a new frontend plugin in the application.
It is the frontend counterpart to the [backend plugin development guide](plugins.md).

The plugin system is designed to be:

- Modular
- Lazy-loaded
- Route-based

> All paths in this guide are relative to the `frontend/` directory.

## Plugin Directory

All plugins live under:

    plugins/

## 1. Defining a new plugin

Create a new folder using the plugin’s **kebab-case** name:

    plugins/<plugin-name>/

**Example:**

    plugins/example-plugin/

## 2. Create the Plugin UI Component

Inside the new plugin directory, create a React component that represents the plugin’s UI.

**File**

    plugins/<plugin-name>/<PluginName>.tsx

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

## 3. Define the Plugin (index.ts)

Each plugin must export a `PluginDefinition` from its own `index.ts`.

**Example Plugin Structure**

```
plugins/
 └─ chat/
    ├─ ChatInterface.tsx
    └─ index.ts
```

**File**

    plugins/<plugin-name>/index.ts

**Example**

```ts
import { PluginDefinition } from "@/lib/plugins/types";

export const examplePlugin: PluginDefinition = {
  name: "example-plugin",
  loadComponent: () => import("./ExamplePlugin"),
};
```

**Note**

A `PluginDefinition` holds only what the frontend alone can own:

- `name` – unique plugin identifier (must match folder and route, **and** the backend plugin's declared name (see "Plugin Names" in the [backend plugin development guide](plugins.md)), so the UI resolves to the right backend plugin)
- `loadComponent` – lazy-loaded UI component
- `loadSettingsComponent` (optional) – custom settings modal

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

Icons cross the wire as [lucide](https://lucide.dev/icons/) icon names. The
resolver in `core/plugins/icons.ts` maps names to components, and only the lucide
names already in that map resolve (icons are mapped explicitly to keep the
bundle tree-shakeable). A backend plugin declaring a new lucide name must also
add it to the map in `core/plugins/icons.ts`, or the UI silently falls
back to an icon-less rendering (the resolver logs a `console.warn` outside
production to surface the gap). A plugin that ships a custom (non-lucide) icon
registers it under its declared name:

```ts
import { registerPluginIcon } from "@/lib/plugins/icons";
import ExampleBrandIcon from "./ExampleBrandIcon";

registerPluginIcon("example-brand", ExampleBrandIcon);
```

For more details, see the `PluginDefinition` type in
[`frontend/core/plugins/types.ts`](https://github.com/edly-io/sparkth/blob/main/frontend/core/plugins/types.ts).

## 4. Publicly Export the Plugin

Expose the plugin from the plugins barrel file.

**File**

    plugins/index.ts

```ts
export * from "./chat"; // already existing

// your plugin export goes here
export * from "./example-plugin";
```

This makes the plugin available for registration.

## 5. Register the Plugin

Register the plugin with the plugin registry.

**File**

    app/plugins.ts

```ts
import { registerPlugin } from "@/core/plugins/registry";
import { chatPlugin, examplePlugin } from "@/plugins";

registerPlugin(chatPlugin); // already existing

// your plugin registration goes here
registerPlugin(examplePlugin);
```

`app/LocaleProvider.tsx` and the dashboard layout import this module, so the plugins are
registered on every page before their catalogs load.

> ⚠️ If a plugin is not registered here, it will not load, not render, and not appear in the sidebar.

## 6. Regenerate the Plugin Route List

Each plugin is rendered under:

    dashboard/<pluginName>

The static routes are **generated from the backend declarations**, not
hand-maintained: `generateStaticParams` in
`app/dashboard/[pluginName]/page.tsx` reads `FRONTEND_PLUGIN_NAMES` from
`core/plugins/generated.ts`, which lists every backend plugin that registered
the `FRONTEND_APPS` hook. After declaring (or removing) a frontend app on the
backend plugin, regenerate the list:

```bash
make frontend.build.plugins
```

**Notes**

- Do not edit `core/plugins/generated.ts` by hand. The dump script is its sole
  formatter, so the file is listed in `.oxfmtrc.json` `ignorePatterns` (as
  `lib/api/generated.ts` already is) — otherwise `make format` would rewrite it
  and break the byte-exact backend gate
- To inspect the dump without touching the committed file, run the script with
  no arguments and it prints to stdout:
  `uv run python scripts/dump_frontend_plugins.py`. The make target passes
  `-o frontend/core/plugins/generated.ts`, which writes atomically, so a failed
  dump leaves the committed file intact
- Tests on both tiers fail when the committed list drifts from the backend
  declarations (`tests/core/test_dump_frontend_plugins.py`) or when the
  frontend registry does not match it (`frontend/tests/app/plugins.test.ts`)
- `PluginPageClient` handles loading the correct plugin dynamically

## Translations (Optional)

A plugin owns its message catalogs, mirroring the backend rule: the core
`messages/*.json` files carry no plugin namespace, and a plugin with
user-facing strings ships its own catalogs under its directory, scoped to a
single top-level namespace equal to the plugin name.

**1. Create the catalogs**

    plugins/example-plugin/messages/en.json
    plugins/example-plugin/messages/es.json
    plugins/example-plugin/messages/fr.json

```json
{
  "example-plugin": {
    "greeting": "Hello from the example plugin"
  }
}
```

Every locale in `lib/i18n/config.ts` needs a file, all carrying the same keys.

**2. Declare the loader on the plugin definition**

```ts
import type { Locale } from "@/lib/i18n/config";

const messageCatalogs: Record<Locale, () => Promise<{ default: Record<string, unknown> }>> = {
  en: () => import("./messages/en.json"),
  es: () => import("./messages/es.json"),
  fr: () => import("./messages/fr.json"),
};

export const examplePlugin: PluginDefinition = {
  name: "example-plugin",
  loadComponent: () => import("./ExamplePlugin"),
  loadMessages: (locale) => messageCatalogs[locale]().then((catalog) => catalog.default),
};
```

`loadMessages` in `lib/i18n/messages.ts` merges every registered plugin's
catalog into the core one at load time; a catalog that fails to load falls
back to the plugin's English one.

**3. Bind the types**

Intersect the plugin's English catalog into the `PluginMessages` type in
`lib/i18n/messages.ts` (type-only, so the plugin stays a self-contained
runtime unit):

```ts
import type examplePluginMessages from "@/plugins/example-plugin/messages/en.json";

type PluginMessages = typeof chatMessages & typeof examplePluginMessages;
```

**4. Use the namespace in components**

```tsx
const t = useTranslations("example-plugin");

<p>{t("greeting")}</p>
```

Plugin components use only their own namespace, never a core one. The catalog
drift guard (`make test.frontend.i18n`) picks the new `messages/` directory up
automatically and checks it against the plugin's own sources, and
`frontend/tests/lib/i18n/messages.test.ts` enforces the namespace containment.
In component tests, pass the plugin catalog to the intl helper:
`renderWithIntl(<ExamplePlugin />, exampleEn)`. See the
[translations guide](translations.md#plugin-catalogs) for the full picture.

## Slots (Optional)

A plugin contributes to a core screen, or to another plugin, through a **slot**. A slot is the frontend counterpart
of a backend hook, such as the one behind [chat capabilities](plugins.md#chat-capabilities). It is called a slot
so it is not confused with a React hook.

A slot keeps each plugin's items under the plugin's name. The code that reads the slot decides which plugins'
items to show, for example only the plugins the user has turned on. Slots are defined in `lib`, the way
backend hooks are defined in `sparkth/lib/`, so core and plugins import a slot from the same path and no plugin
imports another.

**1. Declare the slot** in `lib/<area>/slots.ts`, with the type of item it holds:

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
// plugins/example-plugin/sections.ts
import { EXAMPLE_SECTIONS } from "@/lib/example/slots";

EXAMPLE_SECTIONS.set("example-plugin", [
  { title: "Example", loadComponent: () => import("./ExampleSection") },
]);
```

A file runs only when something imports it, so the plugin's `index.ts` imports it, and the file runs when
`app/plugins.ts` imports the plugin:

```ts
// plugins/example-plugin/index.ts
import "./sections";
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

- Ensure it’s exported from `plugins/index.ts`
- Ensure it’s registered in `app/plugins.ts`

**Plugin page blank?**

- Check `loadComponent` path
- Ensure component is a default export
- Ensure route param matches plugin name
