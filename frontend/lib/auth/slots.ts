/**
 * The slot through which a plugin clears what it keeps in this browser when the user logs out.
 *
 * Logging out runs every handler, whatever page is open, so a plugin doesn't have to be on screen to
 * clean up. A handler must not throw: one that did would stop the logout.
 */

import type { Slot } from "@/lib/slots";

/** The handlers each plugin set, run when the user logs out. */
export const LOGOUT_HANDLERS: Slot<() => void> = new Map();
