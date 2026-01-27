"use client";

import { useState } from "react";
import { Paperclip, Mic, ArrowUp, X, FileText } from "lucide-react";
import { UploadMenu } from "./UploadMenu";
import { TextAttachment } from "../../types";
import { uploadFile, UploadResponse } from "@/lib/file_upload";
import { Pill } from "../attachment/Pill";

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
  const [message, setMessage] = useState("");
  const [showUploadMenu, setShowUploadMenu] = useState(false);

  const handleUploadAsText = async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);

    const data: UploadResponse = await uploadFile(formData);

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
            placeholder="Describe the course you want to create..."
            rows={1}
            className="w-full bg-transparent resize-none focus:outline-none"
          />

          <div className="flex justify-between mt-2">
            <div className="relative">
              <button
                onClick={() => setShowUploadMenu((v) => !v)}
                className="p-2 rounded-lg hover:bg-surface-variant hover:cursor-pointer"
              >
                <Paperclip className="w-5 h-5" />
              </button>

              {showUploadMenu && (
                <UploadMenu
                  onClose={() => setShowUploadMenu(false)}
                  onUploadText={handleUploadAsText}
                />
              )}
            </div>

            <div className="flex gap-1">
              <button className="p-2 rounded-lg hover:bg-surface-variant hover:cursor-pointer">
                <Mic className="w-5 h-5" />
              </button>

              <button
                onClick={handleSend}
                disabled={!message.trim() && !attachment}
                className="p-2 rounded-full bg-foreground text-background enabled:hover:cursor-pointer disabled:opacity-50"
              >
                <ArrowUp className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
