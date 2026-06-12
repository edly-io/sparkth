import { useCallback, useEffect, useState } from "react";
import { listConversations, type ConversationSummary } from "@/lib/chat";

interface UseConversationsResult {
  conversations: ConversationSummary[];
  loading: boolean;
  error: string | null;
  clearError: () => void;
}

export function useConversations(
  token: string | null,
  activeId: string | null,
): UseConversationsResult {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchConversations = useCallback(
    async (signal: AbortSignal) => {
      if (!token) return;
      setLoading(true);
      setError(null);
      try {
        setConversations(await listConversations(token, signal));
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
