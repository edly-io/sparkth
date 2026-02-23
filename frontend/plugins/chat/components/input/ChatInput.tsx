"use client";

import { useState } from "react";
import { Paperclip, ArrowUp } from "lucide-react";
import { UploadMenu } from "./UploadMenu";
import { TextAttachment } from "../../types";
import { uploadFile, UploadResponse } from "@/lib/file_upload";
import { Pill } from "../attachment/Pill";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/lib/auth-context";

interface ChatInputProps {
  attachment: TextAttachment | null;
  setAttachment: (attachment: TextAttachment | null) => void;
  setPreviewAttachment: (attachment: TextAttachment | null) => void;
  setPreviewOpen: (open: boolean) => void;
  onSend: (payload: {
    message: string;
    attachment: TextAttachment | null;
  }) => void;
}

export function ChatInput({
  attachment,
  setAttachment,
  setPreviewAttachment,
  setPreviewOpen,
  onSend,
}: ChatInputProps) {
  const { token } = useAuth();
  const [message, setMessage] = useState("");
  const [showUploadMenu, setShowUploadMenu] = useState(false);

  const handleUploadAsText = async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);

    const data: UploadResponse = await uploadFile(token, formData);

    setAttachment({
      name: file.name,
      size: file.size,
      text: data.text,
    });

    setShowUploadMenu(false);
  };

  const handleSend = () => {
    if (!message.trim() && !attachment) return;

    onSend({
      message: message.trim(),
      attachment,
    });

    setMessage("");
    setAttachment(null);
  };

  return (
    <div className="border-t border-border p-4">
      <div className="mx-auto space-y-2">
        {/* Attachment pill */}
        <Pill
          attachment={attachment}
          onOpen={() => {
            setPreviewAttachment(attachment);
            setPreviewOpen(true);
          }}
          onRemove={() => setAttachment(null)}
        />

        {/* Input box */}
        <div className="relative bg-input border border-border rounded-2xl p-3">
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Describe the course you want to create..."
            rows={1}
            className="w-full bg-transparent resize-none focus:outline-none"
          />

          <div className="flex justify-between mt-2">
            <div className="relative">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowUploadMenu((v) => !v)}
              >
                <Paperclip className="w-5 h-5" />
              </Button>

              {showUploadMenu && (
                <UploadMenu
                  onClose={() => setShowUploadMenu(false)}
                  onUploadText={handleUploadAsText}
                />
              )}
            </div>

            <div className="flex gap-1">
              {/* TODO: Voice input - disabled for now
              <Button variant="ghost" size="icon">
                <Mic className="w-5 h-5" />
              </Button>
              */}

              <Button
                variant="primary"
                size="icon"
                onClick={handleSend}
                disabled={!message.trim() && !attachment}
                className="rounded-full bg-foreground text-background"
              >
                <ArrowUp className="w-5 h-5" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
