// Loads the entry point (src/index.ts) of every folder under plugins/, so adding a plugin is adding
// its folder and no file names it. The bundler lists the matching files at build time, which the
// static export needs; tests swap this module for one that does the same with Vite's glob.

// require.context is the bundler's, not Node's, so its type is declared here.
declare const require: {
  context(
    directory: string,
    useSubdirectories: boolean,
    filter: RegExp,
  ): { keys(): string[]; (id: string): unknown };
};

const pluginEntryPoints = require.context("../plugins", true, /^\.\/[^/]+\/src\/index\.ts$/);
pluginEntryPoints.keys().forEach((key) => pluginEntryPoints(key));

export {};
