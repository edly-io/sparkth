import { useCallback, useEffect, useState } from "react";

interface Conversation {
  id: number;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

interface UseConversationsResult {
  conversations: Conversation[];
  loading: boolean;
  error: string | null;
  clearError: () => void;
}

export function useConversations(
  token: string | null,
  activeId: string | null,
): UseConversationsResult {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchConversations = useCallback(
    async (signal: AbortSignal) => {
      if (!token) return;
      setLoading(true);
      setError(null);
      try {
        const r = await fetch("/api/v1/chat/conversations", {
          headers: { Authorization: `Bearer ${token}` },
          signal,
        });
        if (!r.ok) throw new Error(`Failed to load conversations: HTTP ${r.status}`);
        const data = await r.json();
        setConversations(data.conversations ?? []);
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        console.error(err);
        setError("Failed to load conversations. Please try again.");
      } finally {
        setLoading(false);
      }
    },
    [token],
  );

  useEffect(() => {
    const controller = new AbortController();
    fetchConversations(controller.signal);
    return () => controller.abort();
  }, [fetchConversations, activeId]);

  return { conversations, loading, error, clearError: () => setError(null) };
}
