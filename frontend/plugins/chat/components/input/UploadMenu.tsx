import { FileText } from "lucide-react";
import { useRef } from "react";
import { Button } from "@/components/ui/Button";
import GoogleDriveIcon from "@/plugins/google-drive/GoogleDriveIcon";

interface UploadMenuProps {
  onClose: () => void;
  onUploadText: (file: File) => void;
  isDriveEnabled?: boolean;
  onPickFromDrive?: () => void;
}

export function UploadMenu({
  onClose,
  onUploadText,
  isDriveEnabled,
  onPickFromDrive,
}: UploadMenuProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <>
      <div aria-hidden="true" className="fixed inset-0 z-0" onClick={onClose} />

      <input
        ref={inputRef}
        type="file"
        accept=".txt,.pdf"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) {
            onUploadText(file);
            onClose();
          }
        }}
      />

      <div className="absolute left-0 bottom-full mb-2 bg-input border border-border rounded-xl shadow-lg py-2 min-w-[200px] z-10">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => inputRef.current?.click()}
          className="w-full !justify-start gap-3 rounded-none"
        >
          <FileText className="w-5 h-5" />
          <span className="text-left">Select File</span>
        </Button>
        {isDriveEnabled && onPickFromDrive && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              onPickFromDrive();
              onClose();
            }}
            className="w-full !justify-start gap-3 rounded-none"
          >
            <GoogleDriveIcon className="w-5 h-5" />
            <span className="text-left">Pick from Google Drive</span>
          </Button>
        )}
      </div>
    </>
  );
}
