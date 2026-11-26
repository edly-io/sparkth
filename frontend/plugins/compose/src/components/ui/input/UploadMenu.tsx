import { FileText } from "lucide-react";
import { useRef } from "react";
import { useTranslations } from "next-intl";
import { ATTACHMENT_SOURCES, type AttachmentSource } from "@/plugins/compose/src/slots/attachments";
import { Button } from "@/lib/components/ui/Button";
import { usePlugin } from "@/lib/plugins/context";
import { MAX_COMBINED_UPLOAD_MB } from "@/plugins/compose/src/constants";
import { slotItems } from "@/lib/slots";

interface UploadMenuProps {
  onClose: () => void;
  /** Uploads the files picked from the user's computer. */
  onUploadFromComputer: (files: File[]) => void;
  /** Opens the chosen source's picker. */
  onPickSource: (source: AttachmentSource) => void;
}

function SourceItem({
  plugin,
  source,
  onPick,
}: {
  plugin: string;
  source: AttachmentSource;
  onPick: () => void;
}) {
  const { isUsable } = usePlugin(plugin);
  if (!isUsable) return null;

  const Icon = source.icon;
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={onPick}
      className="w-full !justify-start gap-3 rounded-none"
    >
      <Icon className="w-5 h-5" />
      <span className="text-left">{source.label}</span>
    </Button>
  );
}

/**
 * Compose's attach menu: files from the user's computer, with the file types and total size it
 * takes, then one entry for each attachment source whose plugin is enabled.
 */
export function UploadMenu({ onClose, onUploadFromComputer, onPickSource }: UploadMenuProps) {
  const t = useTranslations("compose");
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <>
      <div aria-hidden="true" className="fixed inset-0 z-0" onClick={onClose} />

      <input
        ref={inputRef}
        type="file"
        accept=".txt,.pdf"
        multiple
        hidden
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          if (files.length > 0) {
            onUploadFromComputer(files);
            onClose();
          }
        }}
      />

      <div className="absolute left-0 bottom-full mb-2 bg-input border border-border rounded-xl shadow-lg py-2 flex flex-col w-max min-w-[200px] z-10">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => inputRef.current?.click()}
          className="w-full !justify-start gap-3 rounded-none"
        >
          <FileText className="w-5 h-5" />
          <span className="flex flex-col text-left">
            {t("selectFiles")}
            <span className="text-xs font-normal text-muted-foreground">
              {t("selectFilesLimit", { limitMb: MAX_COMBINED_UPLOAD_MB })}
            </span>
          </span>
        </Button>
        {slotItems(ATTACHMENT_SOURCES).map(([plugin, source], index) => (
          <SourceItem
            key={`${plugin}:${index}`}
            plugin={plugin}
            source={source}
            onPick={() => {
              onPickSource(source);
              onClose();
            }}
          />
        ))}
      </div>
    </>
  );
}
