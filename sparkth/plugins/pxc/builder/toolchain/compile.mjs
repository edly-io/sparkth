// Compile one sandbox.js against a WIT world: node compile.mjs <source> <wit> <output>
//
// Writes only the cause of a failure to stderr, for the agent that wrote the source. Exit 1
// means the source is at fault. Exit 2 means the toolchain's packages could not be loaded.

import { readFile, writeFile } from "node:fs/promises";

const [sourcePath, witPath, outputPath] = process.argv.slice(2);

let componentize;
let parseAsync;
try {
  ({ componentize } = await import("@bytecodealliance/componentize-js"));
  ({ parseAsync } = await import("oxc-parser"));
} catch (err) {
  process.stderr.write(`${err.message}\n`);
  process.exit(2);
}

// componentize reports only how many syntax errors it found, so parse first to say where.
const { errors } = await parseAsync(sourcePath, await readFile(sourcePath, "utf-8"));
if (errors.length > 0) {
  process.stderr.write(errors.map((error) => error.codeframe).join("\n"));
  process.exit(1);
}

try {
  const { component } = await componentize({
    sourcePath,
    witPath,
    worldName: "activity",
    disableFeatures: ["http", "fetch-event"],
  });
  await writeFile(outputPath, component);
} catch (err) {
  process.stderr.write(`${err.message}\n`);
  process.exit(1);
}
