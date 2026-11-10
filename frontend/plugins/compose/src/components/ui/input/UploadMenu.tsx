import { FileText } from "lucide-react";
import { useRef } from "react";
import { ATTACHMENT_SOURCES, type AttachmentSource } from "@/plugins/compose/src/slots/attachments";
import { Button } from "@/lib/components/ui/Button";
import { usePlugin } from "@/lib/plugins/context";
import { slotItems } from "@/lib/slots";

interface UploadMenuProps {
  onClose: () => void;
  onUploadText: (file: File) => void;
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
  const { isEnabled } = usePlugin(plugin);
  if (!isEnabled) return null;

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
 * Compose's attach menu: a file from the user's computer, then one entry for each attachment
 * source whose plugin is enabled.
 */
export function UploadMenu({ onClose, onUploadText, onPickSource }: UploadMenuProps) {
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
