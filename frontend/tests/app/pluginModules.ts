/// <reference types="vite/client" />
// Stands in for app/pluginModules.ts under Vitest, which has no require.context: loads the same
// entry points, every plugins/<plugin>/src/index.ts, with Vite's glob.
import.meta.glob("@/plugins/*/src/index.ts", { eager: true });
