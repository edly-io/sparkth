"use client";

import { Dispatch, SetStateAction, useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import { Paperclip, ArrowUp, Square, X } from "lucide-react";
import { UploadMenu } from "./UploadMenu";
import { AiKeyProblem, TextAttachment } from "../../types";
import { PersistedFilesInfo } from "../attachment/PersistedFilesInfo";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/lib/auth-context";
import { useIsPluginEnabled } from "@/lib/plugins/usePlugins";
import DriveFilePicker from "@/components/drive/DriveFilePicker";
import { useChatInput } from "../../hooks/useChatInput";

interface ChatInputProps {
  attachments: TextAttachment[];
  setAttachments: Dispatch<SetStateAction<TextAttachment[]>>;
  onSend: (payload: {
    message: string;
    attachments: TextAttachment[];
    documentIds?: number[];
  }) => void;
  conversationId: string | null;
  isStreaming: boolean;
  isStopping: boolean;
  onStop: () => void;
  checkAiKeyReady: () => Promise<AiKeyProblem | null>;
  onAiKeySetupNeeded: (problem: AiKeyProblem) => void;
}

export function ChatInput({
  attachments,
  setAttachments,
  onSend,
  conversationId,
  isStreaming,
  isStopping,
  onStop,
  checkAiKeyReady,
  onAiKeySetupNeeded,
}: ChatInputProps) {
  const t = useTranslations("chat");
  const boxRef = useRef<HTMLTextAreaElement>(null);
  const { token } = useAuth();

  const {
    message,
    setMessage,
    showUploadMenu,
    setShowUploadMenu,
    showDriveFilePicker,
    setShowDriveFilePicker,
    uploadError,
    setUploadError,
    handleUploadAsText,
    handleDriveFileSelected,
    handleRemoveAttachment,
    handleSend,
  } = useChatInput({
    token,
    conversationId,
    attachments,
    setAttachments,
    onSend,
    checkAiKeyReady,
    onAiKeySetupNeeded,
  });

  const { isEnabled: isDriveEnabled } = useIsPluginEnabled(token, "google-drive");

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

        {/* Persisted Drive-file info line */}
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
                  isDriveEnabled={isDriveEnabled}
                  onPickFromDrive={() => setShowDriveFilePicker(true)}
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

      {showDriveFilePicker && (
        <DriveFilePicker
          onClose={() => setShowDriveFilePicker(false)}
          onFileSelected={handleDriveFileSelected}
          initialSelectedFiles={attachments
            .filter((a) => a.driveFileDbId !== undefined)
            .map((a) => ({
              id: a.driveFileDbId!,
              document_id: a.documentId!,
              name: a.name,
              size: a.size,
            }))}
        />
      )}
    </div>
  );
}
