import { ATTACHMENT_SOURCES } from "@/lib/attachments/slots";
import GoogleDriveIcon from "@/plugins/google-drive/GoogleDriveIcon";

ATTACHMENT_SOURCES.set("google-drive", [
  {
    label: "Pick from Google Drive",
    icon: GoogleDriveIcon,
    loadPicker: () => import("@/plugins/google-drive/components/AttachmentPicker"),
  },
]);
