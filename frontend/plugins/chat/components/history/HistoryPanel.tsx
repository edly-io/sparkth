"use client";

import { useState, type ReactElement } from "react";
import Link from "next/link";
import { History, Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/lib/components/ui/Button";
import { Sheet, SheetContent, SheetTitle } from "@/lib/components/ui/Sheet";
import HistoryList from "@/plugins/chat/components/history/HistoryList";

/**
 * The chat history on phones. The header's history button slides the list in over the
 * conversation, and picking a chat closes it.
 */
export default function HistoryPanel(): ReactElement {
  const t = useTranslations("chat");
  const [open, setOpen] = useState(false);

  return (
    <div className="flex items-center gap-1 lg:hidden">
      <Button
        variant="ghost"
        size="icon"
        className="h-9 w-9"
        aria-label={t("historyShow")}
        onClick={() => setOpen(true)}
      >
        <History className="w-5 h-5" />
      </Button>
      <Button asChild variant="ghost" size="icon" className="h-9 w-9">
        <Link href="/dashboard/chat" aria-label={t("historyNewChat")}>
          <Plus className="w-5 h-5" />
        </Link>
      </Button>

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="left" className="p-0 w-72 flex flex-col" aria-describedby={undefined}>
          <SheetTitle className="px-4 pt-4 pb-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            {t("historyTitle")}
          </SheetTitle>
          <HistoryList onNavigate={() => setOpen(false)} />
        </SheetContent>
      </Sheet>
    </div>
  );
}
