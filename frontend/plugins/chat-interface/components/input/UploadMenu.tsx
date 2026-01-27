import { Upload, FileText } from "lucide-react";
import { useRef } from "react";

interface UploadMenuProps {
  onClose: () => void;
  onUploadText: (file: File) => void;
}

export function UploadMenu({ onClose, onUploadText }: UploadMenuProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <>
      <div className="absolute left-0 bottom-full mb-2 bg-input border border-border rounded-xl shadow-lg py-2 min-w-[200px] z-10">
        <button
          onClick={() => inputRef.current?.click()}
          className="w-full px-4 py-2.5 flex items-center gap-3 hover:bg-surface-variant hover:cursor-pointer text-foreground transition-colors"
        >
            <FileText className="w-5 h-5 text-muted-foreground" />
          <span className="text-sm">Upload as Text</span>
          
          <input
            ref={inputRef}
            type="file"
            accept=".txt,.pdf"
            hidden
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) onUploadText(file);
            }}
          />
        </button>
        <button className="w-full px-4 py-2.5 flex items-center gap-3 hover:bg-surface-variant hover:cursor-pointer text-foreground transition-colors">
          <Upload className="w-5 h-5 text-muted-foreground" />
          <span className="text-sm">Upload to Provider</span>
        </button>
      </div>

      <div className="fixed inset-0 z-0" onClick={onClose} />
    </>
  );
}
