"use client";

import type { ReactElement } from "react";
import Link from "next/link";
import { MessageSquare } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import { Spinner } from "@/lib/components/ui/Spinner";
import { Alert } from "@/components/ui/Alert";
import { useAuth } from "@/lib/auth/hooks";
import type { ConversationSummary } from "@/lib/compose";
import { useActiveConversationId } from "@/plugins/compose/hooks/useActiveConversationId";
import { useConversations } from "@/plugins/compose/hooks/useConversations";

const DAY_MS = 86_400_000;
const RELATIVE_DAYS = 7;

interface HistoryListProps {
  onNavigate?: () => void;
}

interface ConversationLinkProps {
  conversation: ConversationSummary;
  isActive: boolean;
  onNavigate?: () => void;
}

function startOfLocalDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

/**
 * Whole calendar days from `created` to today in the browser's timezone. Rounding absorbs
 * 23- and 25-hour DST days, and a timestamp slightly ahead of the browser clock counts as today.
 */
function calendarDaysAgo(created: Date): number {
  const days = Math.round((startOfLocalDay(new Date()) - startOfLocalDay(created)) / DAY_MS);
  return Math.max(0, days);
}

/** A conversation's creation time: today, yesterday, N days ago, then a short localized date. */
function ConversationDate({ iso }: { iso: string }): string {
  const t = useTranslations("compose");
  const format = useFormatter();
  const created = new Date(iso);
  const days = calendarDaysAgo(created);

  if (days === 0) return t("historyToday");
  if (days === 1) return t("historyYesterday");
  if (days < RELATIVE_DAYS) return t("historyDaysAgo", { count: days });
  return format.dateTime(created, { month: "short", day: "numeric" });
}

function ConversationLink({
  conversation,
  isActive,
  onNavigate,
}: ConversationLinkProps): ReactElement {
  const t = useTranslations("compose");

  return (
    <Link
      href={`/dashboard/compose?id=${conversation.id}`}
      onClick={onNavigate}
      aria-current={isActive ? "page" : undefined}
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
          {conversation.title || t("historyUntitled")}
        </p>
        <p className="text-[11px] text-muted-foreground mt-0.5">
          <ConversationDate iso={conversation.created_at} />
        </p>
      </div>
    </Link>
  );
}

/** The signed-in user's conversations, newest first, linking to each one in the chat page. */
export default function HistoryList({ onNavigate }: HistoryListProps): ReactElement {
  const t = useTranslations("compose");
  const { token } = useAuth();
  const activeId = useActiveConversationId();
  const { conversations, loading, error, clearError } = useConversations(token, activeId);

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {error && (
        <div className="px-3 pt-3">
          <Alert severity="error" title={t("historyErrorTitle")} onClose={clearError}>
            {t("historyLoadError")}
          </Alert>
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-0.5">
        {loading ? (
          <div className="flex items-center justify-center py-4">
            <Spinner size="sm" className="text-muted-foreground" />
          </div>
        ) : conversations.length === 0 ? (
          <p className="text-xs text-muted-foreground px-2 py-3 text-center">{t("historyEmpty")}</p>
        ) : (
          conversations.map((conversation) => (
            <ConversationLink
              key={conversation.id}
              conversation={conversation}
              isActive={activeId === String(conversation.id)}
              onNavigate={onNavigate}
            />
          ))
        )}
      </div>
    </div>
  );
}
