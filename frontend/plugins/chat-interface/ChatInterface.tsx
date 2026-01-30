"use client";

import { useState } from "react";
import { Send, Paperclip, Bot } from "lucide-react";
import { Card } from "@/components/ui/Card";

export default function ChatInterface() {
  const [message, setMessage] = useState("");

  return (
    <div className="flex flex-col h-full bg-background transition-colors">
      <div className="border-b border-border px-6 py-4">
        <div className="flex items-center gap-3">
          <div>
            <h2 className="text-lg font-semibold text-foreground">
              AI Course Creator
            </h2>
            <p className="text-sm text-muted-foreground">
              Transform your resources into courses with AI
            </p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto">
          <div className="flex gap-4">
            <div className="w-8 h-8 rounded-full bg-neutral-200 dark:bg-neutral-700 flex items-center justify-center flex-shrink-0">
              <span className="text-sm">
                <Bot className="w-4 h-4" />
              </span>
            </div>
            <div className="flex-1">
              <Card variant="outlined" className="p-4">
                <p className="text-foreground">
                  Hi! I am your AI course creation assistant. I can help you
                  transform your resources into engaging courses. What would you
                  like to create today?
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <button className="px-4 py-2 bg-surface-variant hover:bg-neutral-200 dark:hover:bg-neutral-700 rounded-lg text-sm text-muted-foreground transition-colors">
                    Create a course from my course materials folder
                  </button>
                  <button className="px-4 py-2 bg-surface-variant hover:bg-neutral-200 dark:hover:bg-neutral-700 rounded-lg text-sm text-muted-foreground transition-colors">
                    Generate a quiz from my document
                  </button>
                  <button className="px-4 py-2 bg-surface-variant hover:bg-neutral-200 dark:hover:bg-neutral-700 rounded-lg text-sm text-muted-foreground transition-colors">
                    Build a module about AI fundamentals
                  </button>
                  <button className="px-4 py-2 bg-surface-variant hover:bg-neutral-200 dark:hover:bg-neutral-700 rounded-lg text-sm text-muted-foreground transition-colors">
                    Convert my video into a structured lesson
                  </button>
                </div>
              </Card>
              <p className="text-xs mt-2 text-muted-foreground">
                {new Date().toLocaleTimeString("en-US", {
                  hour: "numeric",
                  minute: "2-digit",
                  second: "2-digit",
                  hour12: true,
                })}
              </p>
            </div>
          </div>
        </div>
      </div>

      <Card
        variant="filled"
        className="border-t border-border rounded-none p-4"
      >
        <div className="mx-auto">
          <div className="relative">
            <button className="absolute left-3 top-1/2 -translate-y-1/2 p-2 rounded-lg hover:bg-surface-variant hover:cursor-pointer transition-colors">
              <Paperclip className="w-5 h-5 text-muted-foreground" />
            </button>

            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Describe the course you want to create..."
              rows={1}
              className="w-full px-12 py-3 border border-border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-ring bg-input text-foreground placeholder-muted transition-colors"
            />

            <button className="absolute right-3 top-1/2 -translate-y-1/2 p-2 rounded-lg hover:bg-surface-variant hover:cursor-pointer transition-colors">
              <Send className="w-5 h-5 text-muted-foreground" />
            </button>
          </div>
        </div>
      </Card>
    </div>
  );
}
