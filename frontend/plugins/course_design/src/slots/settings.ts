import { SettingsListItem } from "@/lib/components/settings/SettingsListItem";
import { SETTINGS_ITEMS } from "@/lib/settings/slots";
import { COURSE_DESIGN_PLUGIN_NAME } from "@/plugins/course_design/src/constants";

// Course design's row on the settings page: an on/off switch, and no config modal since it has no config.
SETTINGS_ITEMS.set(COURSE_DESIGN_PLUGIN_NAME, { listItem: SettingsListItem });
