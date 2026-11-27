"use client";

import { useFormatter, useTranslations } from "next-intl";
import { ConfirmDialog } from "@/core/components/ui/ConfirmDialog";
import { formatRoleName, getRoleHolders } from "@/core/permissions/roleDisplay";
import type { RoleResponse } from "@/core/permissions/types";

/**
 * Asks before deleting `role`, saying how many groups and people will lose it, and runs `onConfirm`
 * when confirmed. Stays open with the error when deleting fails.
 */
export function DeleteRoleDialog({
  role,
  onConfirm,
  onClose,
}: {
  role: RoleResponse;
  onConfirm: () => Promise<void>;
  onClose: () => void;
}) {
  const t = useTranslations("permissions.roles");
  const format = useFormatter();
  const holders = getRoleHolders(role, t);
  return (
    <ConfirmDialog
      title={t("delete.title", { name: formatRoleName(role.name) })}
      description={
        holders.length > 0
          ? t("delete.holders", { holders: format.list(holders) })
          : t("delete.nobody")
      }
      confirmLabel={t("delete.confirm")}
      pendingLabel={t("delete.pending")}
      cancelLabel={t("cancel")}
      errorMessage={t("delete.failed")}
      onConfirm={onConfirm}
      onClose={onClose}
    />
  );
}
