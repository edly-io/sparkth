/** Compose's plugin name, the name its backend plugin declares. */
export const COMPOSE_PLUGIN_NAME = "compose";

/** How many megabytes of computer files one conversation can carry; documents don't count. */
export const MAX_COMBINED_UPLOAD_MB = 3;
/** The same limit in bytes, which is what a file's size is measured in. */
export const MAX_COMBINED_UPLOAD_BYTES = MAX_COMBINED_UPLOAD_MB * 1024 * 1024;
