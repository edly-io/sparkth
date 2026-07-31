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
- Can use plugin context via `usePlugins()` or `createPluginContext`
- This component is lazy-loaded

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
import { PluginDefinition } from "@/lib/plugins";

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
as a string can still arrive as an array or a number. Narrow at the read site
with the helpers in `@/lib/plugins/config` — `configString(config, key)` for a
single text field (non-strings fall back to `undefined` rather than coercing),
and `stringConfigOf(config)` for an editor that renders every field as an input.

Icons cross the wire as [lucide](https://lucide.dev/icons/) icon names. The
resolver in `@/lib/plugins/icons` maps names to components, and only the lucide
names already in that map resolve (icons are mapped explicitly to keep the
bundle tree-shakeable). A backend plugin declaring a new lucide name must also
add it to the map in `frontend/lib/plugins/icons.ts`, or the UI silently falls
back to an icon-less rendering (the resolver logs a `console.warn` outside
production to surface the gap). A plugin that ships a custom (non-lucide) icon
registers it under its declared name:

```ts
import { registerPluginIcon } from "@/lib/plugins/icons";
import ExampleBrandIcon from "./ExampleBrandIcon";

registerPluginIcon("example-brand", ExampleBrandIcon);
```

For more details, see the `PluginDefinition` type in
[`frontend/lib/plugins/types.ts`](https://github.com/edly-io/sparkth/blob/main/frontend/lib/plugins/types.ts).

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

    @/lib/plugins/index.ts

```ts
import { registerPlugin } from "./registry";
import { chatPlugin, examplePlugin } from "@/plugins";

registerPlugin(chatPlugin); // already existing

// your plugin registration goes here
registerPlugin(examplePlugin);

export * from "./registry";
export * from "./types";
export * from "./usePlugins";
export * from "./metadata";
export * from "./config";
export * from "./icons";
```

> ⚠️ If a plugin is not registered here, it will not load, not render, and not appear in the sidebar.

## 6. Regenerate the Plugin Route List

Each plugin is rendered under:

    dashboard/<pluginName>

The static routes are **generated from the backend declarations**, not
hand-maintained: `generateStaticParams` in
`app/dashboard/[pluginName]/page.tsx` reads `FRONTEND_PLUGIN_NAMES` from
`lib/plugins/generated.ts`, which lists every backend plugin that registered
the `FRONTEND_APPS` hook. After declaring (or removing) a frontend app on the
backend plugin, regenerate the list:

```bash
make frontend.build.plugins
```

**Notes**

- Do not edit `lib/plugins/generated.ts` by hand
- Tests on both tiers fail when the committed list drifts from the backend
  declarations (`tests/core/test_dump_frontend_plugins.py`) or when the
  frontend registry does not match it (`lib/tests/plugin-registry-drift.test.ts`)
- `PluginPageClient` handles loading the correct plugin dynamically

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
- Ensure it’s registered in `lib/plugins/index.ts`

**Plugin page blank?**

- Check `loadComponent` path
- Ensure component is a default export
- Ensure route param matches plugin name
