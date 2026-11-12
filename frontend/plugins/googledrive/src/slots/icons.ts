import { Folder } from "lucide-react";

import { PLUGIN_ICONS } from "@/lib/icons/slots";
import { GOOGLEDRIVE_PLUGIN_NAME } from "@/plugins/googledrive/src/constants";

// The backend GoogleDrivePlugin declares its sidebar icon as "folder".
PLUGIN_ICONS.set(GOOGLEDRIVE_PLUGIN_NAME, [{ name: "folder", component: Folder }]);
