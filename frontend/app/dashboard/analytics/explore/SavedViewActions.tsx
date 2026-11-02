"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import type { ExploreConfig } from "@/lib/analytics";
import { Button } from "@/core/components/ui/Button";
import { SaveViewDialog } from "./SaveViewDialog";
import type { SavedView } from "./useSavedView";

/**
 * The toolbar for saving `config`: Save view when no view is open; otherwise Save, Save as new,
 * Rename and Delete (after a confirm) on the open view.
 */
export function SavedViewActions({ saved, config }: { saved: SavedView; config: ExploreConfig }) {
  const t = useTranslations("analytics.explore");
  const [dialog, setDialog] = useState<"create" | "rename" | null>(null);
  const { view } = saved;

  const remove = () => {
    if (view && confirm(t("confirmDelete", { name: view.name }))) void saved.remove(config);
  };

  return (
    <div className="flex flex-wrap gap-2">
      {view ? (
        <>
          <Button size="sm" onClick={() => void saved.save(config)}>
            {t("save")}
          </Button>
          <Button size="sm" variant="secondary" onClick={() => setDialog("create")}>
            {t("saveAsNew")}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setDialog("rename")}>
            {t("rename")}
          </Button>
          <Button size="sm" variant="ghost" onClick={remove}>
            {t("delete")}
          </Button>
        </>
      ) : (
        <Button size="sm" onClick={() => setDialog("create")}>
          {t("saveView")}
        </Button>
      )}
      <SaveViewDialog
        open={dialog !== null}
        title={dialog === "rename" ? t("renameView") : t("saveView")}
        initialName={dialog === "rename" ? view?.name : ""}
        onSave={dialog === "rename" ? saved.rename : (name) => saved.saveNew(name, config)}
        onClose={() => setDialog(null)}
      />
    </div>
  );
}
