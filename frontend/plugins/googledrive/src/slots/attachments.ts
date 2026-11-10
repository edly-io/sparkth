import { ATTACHMENT_SOURCES } from "@/lib/attachments/slots";
import GoogleDriveIcon from "@/plugins/googledrive/src/components/ui/GoogleDriveIcon";

ATTACHMENT_SOURCES.set("google-drive", [
  {
    label: "Pick from Google Drive",
    icon: GoogleDriveIcon,
    loadPicker: () => import("@/plugins/googledrive/src/components/ui/AttachmentPicker"),
  },
]);
