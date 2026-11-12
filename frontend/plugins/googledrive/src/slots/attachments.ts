import { ATTACHMENT_SOURCES } from "@/lib/attachments/slots";
import GoogleDriveIcon from "@/plugins/googledrive/src/components/ui/GoogleDriveIcon";
import { GOOGLEDRIVE_PLUGIN_NAME } from "@/plugins/googledrive/src/constants";

ATTACHMENT_SOURCES.set(GOOGLEDRIVE_PLUGIN_NAME, [
  {
    label: "Pick from Google Drive",
    icon: GoogleDriveIcon,
    loadPicker: () => import("@/plugins/googledrive/src/components/ui/AttachmentPicker"),
  },
]);
