import { X } from "lucide-react";
import { TextAttachment } from "../../types";

export function Preview({
  attachment,
  onClose,
}: {
  attachment: TextAttachment;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center">
      <div className="bg-background w-full max-w-3xl max-h-[80vh] rounded-xl shadow-lg flex flex-col">
        <div className="flex items-center justify-between p-4 border-b">
          <h3 className="font-medium">{attachment.name}</h3>
          <button onClick={onClose} className="hover:cursor-pointer">
            <X className="w-5 h-5 hover:cursor-pointer" />
          </button>
        </div>

        <div className="p-4 overflow-y-auto text-sm whitespace-pre-wrap">
          {attachment.text}
        </div>
      </div>
    </div>
  );
}
