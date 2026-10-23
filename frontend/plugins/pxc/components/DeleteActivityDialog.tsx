"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/lib/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { ApiRequestError } from "@/lib/api";
import { useAuth } from "@/lib/auth/hooks";
import { deleteActivity, type ActivitySummary } from "@/plugins/pxc/client";

/**
 * Confirmation dialog for permanently deleting a PXC activity.
 *
 * Warns more strongly when the activity has been placed in a course. An activity that is already
 * gone (404) counts as deleted. Any other failure keeps the dialog open with an error.
 */
export function DeleteActivityDialog({
  activity,
  onClose,
  onDeleted,
}: {
  activity: ActivitySummary;
  onClose: () => void;
  onDeleted: (id: string) => void;
}): React.JSX.Element {
  const t = useTranslations("pxc");
  const { token } = useAuth();
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);

  async function handleDelete() {
    if (!token) return;
    setLoading(true);
    setFailed(false);
    try {
      await deleteActivity(token, activity.id);
      onDeleted(activity.id);
    } catch (error) {
      if (error instanceof ApiRequestError && error.status === 404) {
        onDeleted(activity.id);
      } else {
        console.error("pxc: failed to delete activity", error);
        setFailed(true);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && !loading && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("deleteTitle", { title: activity.title })}</DialogTitle>
          <DialogDescription>
            {activity.placed ? t("deletePlacedBody") : t("deleteDraftBody")}
          </DialogDescription>
        </DialogHeader>

        {failed && <Alert severity="error">{t("deleteFailed")}</Alert>}

        <DialogFooter className="gap-2">
          <Button variant="outline" size="sm" onClick={onClose} disabled={loading}>
            {t("cancel")}
          </Button>
          <Button
            variant="error"
            size="sm"
            loading={loading}
            spinnerLabel={t("deleting")}
            disabled={loading}
            onClick={handleDelete}
          >
            {t("delete")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
