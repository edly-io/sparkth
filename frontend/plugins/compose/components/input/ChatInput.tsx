"use client";

import { Dispatch, SetStateAction, Suspense, lazy, useEffect, useMemo, useRef } from "react";
import { useTranslations } from "next-intl";
import { Paperclip, ArrowUp, Square, X } from "lucide-react";
import { UploadMenu } from "@/plugins/compose/components/input/UploadMenu";
import { TextAttachment } from "@/plugins/compose/types";
import { PersistedFilesInfo } from "@/plugins/compose/components/attachment/PersistedFilesInfo";
import { PickerErrorBoundary } from "@/plugins/compose/components/input/PickerErrorBoundary";
import { Button } from "@/lib/components/ui/Button";
import { useAuth } from "@/lib/auth/hooks";
import { useChatInput } from "@/plugins/compose/hooks/useChatInput";

interface ChatInputProps {
  message: string;
  setMessage: Dispatch<SetStateAction<string>>;
  attachments: TextAttachment[];
  setAttachments: Dispatch<SetStateAction<TextAttachment[]>>;
  onSend: (payload: {
    message: string;
    attachments: TextAttachment[];
    documentIds?: number[];
  }) => Promise<boolean>;
  conversationId: string | null;
  isStreaming: boolean;
  isStopping: boolean;
  onStop: () => void;
}

export function ChatInput({
  message,
  setMessage,
  attachments,
  setAttachments,
  onSend,
  conversationId,
  isStreaming,
  isStopping,
  onStop,
}: ChatInputProps) {
  const t = useTranslations("compose");
  const boxRef = useRef<HTMLTextAreaElement>(null);
  const { token } = useAuth();

  const {
    showUploadMenu,
    setShowUploadMenu,
    pickingFrom,
    setPickingFrom,
    uploadError,
    setUploadError,
    handleUploadAsText,
    handleDocumentsSelected,
    handleRemoveAttachment,
    handleSend,
  } = useChatInput({
    message,
    setMessage,
    token,
    conversationId,
    attachments,
    setAttachments,
    onSend,
  });

  // The chosen source's picker, loaded only once the user picks from it.
  const loadPicker = pickingFrom?.loadPicker;
  const Picker = useMemo(() => (loadPicker ? lazy(loadPicker) : null), [loadPicker]);

  // Grow with the text. The reset lets the box shrink again when lines are removed, and CSS caps
  // it at five lines, so the cap and the scrollbar cannot disagree.
  useEffect(() => {
    const box = boxRef.current;
    if (!box) return;
    box.style.height = "auto";
    box.style.height = `${box.scrollHeight}px`;
  }, [message]);

  return (
    <div className="border-t border-border p-4">
      <div className="mx-auto space-y-2">
        {/* Upload error */}
        {uploadError && (
          <div className="flex items-center justify-between gap-2 px-3 py-2 rounded-lg text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/30">
            <span className="truncate">{uploadError}</span>
            <button onClick={() => setUploadError(null)} className="shrink-0">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Persisted document info line */}
        <PersistedFilesInfo attachments={attachments} onDetachFile={handleRemoveAttachment} />

        {/* Input box */}
        <div className="relative bg-input border border-border rounded-2xl p-3">
          <textarea
            ref={boxRef}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (isStreaming) return;
                handleSend();
              }
            }}
            placeholder={t("inputPlaceholder")}
            rows={1}
            className="w-full bg-transparent resize-none focus:outline-none leading-6 max-h-30 overflow-y-auto"
          />

          <div className="flex justify-between mt-2">
            <div className="relative">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowUploadMenu(!showUploadMenu)}
              >
                <Paperclip className="w-5 h-5" />
              </Button>

              {showUploadMenu && (
                <UploadMenu
                  onClose={() => setShowUploadMenu(false)}
                  onUploadText={handleUploadAsText}
                  onPickSource={setPickingFrom}
                />
              )}
            </div>

            <div className="flex gap-1">
              {/* TODO: Voice input - disabled for now
              <Button variant="ghost" size="icon">
                <Mic className="w-5 h-5" />
              </Button>
              */}

              {isStreaming ? (
                <Button
                  variant="primary"
                  size="icon"
                  aria-label={t("stopGenerating")}
                  onClick={onStop}
                  disabled={isStopping}
                  className="rounded-full bg-foreground text-background"
                >
                  <Square className="w-4 h-4" />
                </Button>
              ) : (
                <Button
                  variant="primary"
                  size="icon"
                  onClick={handleSend}
                  disabled={!message.trim() && attachments.every((a) => a.documentId !== undefined)}
                  className="rounded-full bg-foreground text-background"
                >
                  <ArrowUp className="w-5 h-5" />
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>

      {Picker && (
        <PickerErrorBoundary
          onError={() => {
            setPickingFrom(null);
            setUploadError(t("pickerFailed"));
          }}
        >
          <Suspense fallback={null}>
            <Picker
              onClose={() => setPickingFrom(null)}
              onSelect={handleDocumentsSelected}
              selected={attachments
                .filter((a) => a.sourceId !== undefined && a.documentId !== undefined)
                .map((a) => ({
                  documentId: a.documentId!,
                  sourceId: a.sourceId!,
                  name: a.name,
                  size: a.size,
                }))}
            />
          </Suspense>
        </PickerErrorBoundary>
      )}
    </div>
  );
}
