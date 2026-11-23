import { LOGOUT_HANDLERS } from "@/lib/auth/slots";
import { COMPOSE_PLUGIN_NAME } from "@/plugins/compose/src/constants";
import { clearStoredFiles } from "@/plugins/compose/src/storedFiles";

// The text of uploaded files must not outlive the session on a shared computer.
LOGOUT_HANDLERS.set(COMPOSE_PLUGIN_NAME, [clearStoredFiles]);
