"use client";

import { useEffect, useState } from "react";
import { MessageSquare, Plus } from "lucide-react";
import { Spinner } from "@/components/Spinner";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";

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
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchConversations = async () => {
      setLoading(true);
      setError(null);
      fetch("/api/v1/chat/conversations", {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((r) => {
          if (!r.ok)
            throw new Error(`Failed to load conversations: HTTP ${r.status}`);
          return r.json();
        })
        .then((data) => {
          if (!cancelled) setConversations(data.conversations ?? []);
        })
        .catch((err) => {
          console.error(err);
          setError("Failed to load conversations. Please try again.");
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    };
    fetchConversations();
    return () => {
      cancelled = true;
    };
  }, [token, activeId]);

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
      {error && (
        <div className="px-4 pt-4">
          <Alert
            severity="error"
            title="Something went wrong"
            onClose={() => setError(null)}
          >
            {error}
          </Alert>
        </div>
      )}

      <div className="overflow-y-auto max-h-64 px-3 pb-3 space-y-0.5">
        {loading ? (
          <div className="flex items-center justify-center py-4">
            <Spinner size="sm" className="text-muted-foreground" />
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
