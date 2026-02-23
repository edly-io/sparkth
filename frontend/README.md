# Frontend Plugin Implementation Guide

This document explains how to implement and register a new frontend plugin in the application.

The plugin system is designed to be:

- Modular
- Lazy-loaded
- Route-based

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
import { MessageSquare } from "lucide-react";

export const examplePlugin: PluginDefinition = {
  name: "example-plugin",
  displayName: "Example Plugin",
  description: "Example plugin integration",
  isCore: true,

  loadComponent: () => import("./ExamplePlugin"),

  showInSidebar: true,
  sidebarIcon: MessageSquare,
  sidebarLabel: "Example",
  sidebarOrder: 1,
};
```

**Note**

At a minimum, a plugin must define:

- `name` – unique plugin identifier (must match folder and route)
- `displayName` – user-facing name
- `description` – short description
- `loadComponent` – lazy-loaded UI component

For more details, see `PluginDefinition` defined [here](./lib/plugins/types.ts).

## 4. Publicly Export the Plugin

Expose the plugin from the plugins barrel file.

**File**

    plugins/index.ts

```ts
export * from "./chat";  // already existing

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
```
> ⚠️ If a plugin is not registered here, it will not load, not render, and not appear in the sidebar.


## 6. Add the Plugin Route

Each plugin is rendered under:

    dashboard/<pluginName>


Add a dynamic route for the plugin.

**File**

    app/dashboard/[pluginName]/page.tsx

```ts
import PluginPageClient from "./page-client";

export function generateStaticParams() {
  return [
    { pluginName: "chat" },
    { pluginName: "example-plugin" }  // register your route here
 ];
}

export default function PluginPage() {
  return <PluginPageClient />;
}
```

**Notes**

- `pluginName` must match the plugin name
- `PluginPageClient` handles loading the correct plugin dynamically
- Required for static builds

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
