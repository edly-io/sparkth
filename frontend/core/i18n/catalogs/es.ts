import analytics from "@/core/analytics/i18n/es.json";
import audit from "@/core/audit/i18n/es.json";
import auth from "@/core/auth/i18n/es.json";
import app from "@/core/i18n/es.json";
import llm from "@/core/llm/i18n/es.json";
import settings from "@/core/settings/i18n/es.json";

/** Every core feature's catalog for this locale, merged into the one catalog the loader fetches. */
export default { ...analytics, ...audit, ...auth, ...app, ...llm, ...settings };
