"use client";

import { useEffect, useState } from "react";
import { MessageSquare, Loader2, Plus } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/Button";

interface Conversation {
  id: number;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

interface ChatHistorySectionProps {
  isCollapsed: boolean;
  onNavigate?: () => void;
}

function formatDate(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  const diffDays = Math.floor((now.getTime() - d.getTime()) / 86_400_000);
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays}d ago`;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function ChatHistorySection({
  isCollapsed,
  onNavigate,
}: ChatHistorySectionProps) {
  const { token } = useAuth();
  const searchParams = useSearchParams();
  const activeId = searchParams.get("id");

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/v1/chat/conversations", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((data) => setConversations(data.conversations ?? []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [token]);

  if (isCollapsed) {
    return (
      <div className="px-3 py-2 border-t border-border">
        <Link href="/dashboard/chat" onClick={onNavigate}>
          <Button
            variant="ghost"
            size="icon"
            title="New chat"
            className="w-full flex justify-center"
          >
            <Plus className="w-4 h-4" />
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="border-t border-border flex flex-col min-h-0">
      <div className="flex items-center justify-between px-4 pt-3 pb-1">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Recent chats
        </span>
        <Link href="/dashboard/chat" onClick={onNavigate}>
          <Button
            variant="ghost"
            size="icon"
            title="New chat"
            className="h-6 w-6"
          >
            <Plus className="w-3.5 h-3.5" />
          </Button>
        </Link>
      </div>

      <div className="overflow-y-auto max-h-64 px-3 pb-3 space-y-0.5">
        {loading ? (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
          </div>
        ) : conversations.length === 0 ? (
          <p className="text-xs text-muted-foreground px-2 py-3 text-center">
            No previous chats
          </p>
        ) : (
          conversations.map((c) => {
            const isActive = activeId === String(c.id);
            return (
              <Link
                key={c.id}
                href={`/dashboard/chat?id=${c.id}`}
                onClick={onNavigate}
                className={`
                  w-full flex items-start gap-2 px-2 py-2 rounded-lg transition-colors
                  ${
                    isActive
                      ? "bg-primary-500/15 text-primary-600 dark:text-primary-400"
                      : "text-foreground hover:bg-surface-variant"
                  }
                `}
              >
                <MessageSquare className="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium truncate leading-tight">
                    {c.title || "Untitled"}
                  </p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {formatDate(c.created_at)}
                  </p>
                </div>
              </Link>
            );
          })
        )}
      </div>
    </div>
  );
}
