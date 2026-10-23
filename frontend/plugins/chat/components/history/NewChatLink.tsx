"use client";

import type { ReactElement } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/lib/components/ui/Button";
import { ActionTooltip } from "@/plugins/chat/components/history/ActionTooltip";

interface NewChatLinkProps {
  onNavigate?: () => void;
}

/** An icon link that opens a fresh conversation. */
export function NewChatLink({ onNavigate }: NewChatLinkProps): ReactElement {
  const t = useTranslations("chat");

  return (
    <ActionTooltip label={t("historyNewChat")}>
      <Button asChild variant="ghost" size="icon" className="h-8 w-8">
        <Link href="/dashboard/chat" onClick={onNavigate} aria-label={t("historyNewChat")}>
          <Plus className="w-4 h-4" />
        </Link>
      </Button>
    </ActionTooltip>
  );
}
