"use client";

import type { ReactElement } from "react";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/lib/components/ui/Button";
import { ActionTooltip } from "@/plugins/chat/components/history/ActionTooltip";
import HistoryList from "@/plugins/chat/components/history/HistoryList";
import { NewChatLink } from "@/plugins/chat/components/history/NewChatLink";
import { useHistoryCollapsed } from "@/plugins/chat/hooks/useHistoryCollapsed";

interface ToggleProps {
  label: string;
  onClick: () => void;
  children: ReactElement;
}

function HistoryToggle({ label, onClick, children }: ToggleProps): ReactElement {
  return (
    <ActionTooltip label={label}>
      <Button variant="ghost" size="icon" className="h-8 w-8" aria-label={label} onClick={onClick}>
        {children}
      </Button>
    </ActionTooltip>
  );
}

/**
 * The chat page's "Recent chats" column on desktop. It collapses to a thin rail that keeps the
 * show-history and new-chat actions, and each browser remembers which state it was left in.
 */
export default function HistoryColumn(): ReactElement {
  const t = useTranslations("chat");
  const [collapsed, setCollapsed] = useHistoryCollapsed();

  if (collapsed) {
    return (
      <aside
        aria-label={t("historyTitle")}
        className="hidden lg:flex flex-col items-center gap-1 w-12 shrink-0 py-3 border-r border-border"
      >
        <HistoryToggle label={t("historyShow")} onClick={() => setCollapsed(false)}>
          <PanelLeftOpen className="w-4 h-4" />
        </HistoryToggle>
        <NewChatLink />
      </aside>
    );
  }

  return (
    <aside
      aria-label={t("historyTitle")}
      className="hidden lg:flex flex-col w-64 shrink-0 min-h-0 border-r border-border"
    >
      <div className="flex items-center justify-between px-4 pt-3 pb-1">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          {t("historyTitle")}
        </span>
        <div className="flex items-center gap-1">
          <NewChatLink />
          <HistoryToggle label={t("historyHide")} onClick={() => setCollapsed(true)}>
            <PanelLeftClose className="w-4 h-4" />
          </HistoryToggle>
        </div>
      </div>
      <HistoryList />
    </aside>
  );
}
