"use client";

import { useTranslations } from "next-intl";

import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { ApiRequestError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
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

  async function handleDelete() {
    if (!token) throw new Error("not signed in");
    try {
      await deleteActivity(token, activity.id);
    } catch (error) {
      if (!(error instanceof ApiRequestError && error.status === 404)) throw error;
    }
    onDeleted(activity.id);
  }

  return (
    <ConfirmDialog
      title={t("deleteTitle", { title: activity.title })}
      description={activity.placed ? t("deletePlacedBody") : t("deleteDraftBody")}
      confirmLabel={t("delete")}
      pendingLabel={t("deleting")}
      cancelLabel={t("cancel")}
      errorMessage={t("deleteFailed")}
      onConfirm={handleDelete}
      onClose={onClose}
    />
  );
}
