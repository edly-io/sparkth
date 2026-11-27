"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { ApiRequestError } from "@/lib/api";
import { Button } from "@/core/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/core/components/ui/Dialog";
import { RoleDetailsFields } from "@/core/permissions/components/ui/RoleDetailsFields";
import type { RoleResponse, RoleUpdate } from "@/core/permissions/types";

type RoleDetails = Pick<RoleResponse, "name" | "description">;

/**
 * Edits a role's name and description, starting from `role`'s. Save is enabled once either changes
 * and the name isn't blank, and calls `onSave` with only what changed, trimmed. Closes once saved;
 * stays open with a message when the name is taken or saving fails.
 */
export function EditRoleDialog({
  open,
  role,
  onSave,
  onClose,
}: {
  open: boolean;
  role: RoleDetails;
  onSave: (details: RoleUpdate) => Promise<void>;
  onClose: () => void;
}) {
  const t = useTranslations("permissions.roles.edit");
  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="sm:max-w-md md:max-w-md lg:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("title")}</DialogTitle>
        </DialogHeader>
        {/* Mounted per opening, so the form starts from the role's details each time. */}
        <DetailsForm role={role} onSave={onSave} onClose={onClose} />
      </DialogContent>
    </Dialog>
  );
}

function DetailsForm({
  role,
  onSave,
  onClose,
}: {
  role: RoleDetails;
  onSave: (details: RoleUpdate) => Promise<void>;
  onClose: () => void;
}) {
  const t = useTranslations("permissions.roles");
  const [name, setName] = useState(role.name);
  const [description, setDescription] = useState(role.description ?? "");
  const [nameError, setNameError] = useState<string>();
  const [saveFailed, setSaveFailed] = useState(false);
  const [saving, setSaving] = useState(false);
  const changes: RoleUpdate = {
    ...(name.trim() !== role.name && { name: name.trim() }),
    ...(description.trim() !== (role.description ?? "") && { description: description.trim() }),
  };
  const changed = Object.keys(changes).length > 0;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setNameError(undefined);
    setSaveFailed(false);
    try {
      await onSave(changes);
      onClose();
    } catch (error) {
      if (error instanceof ApiRequestError && error.status === 409) {
        setNameError(t("form.nameTaken"));
      } else {
        console.error("Saving the role's details failed:", error);
        setSaveFailed(true);
      }
      setSaving(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <RoleDetailsFields
        name={name}
        description={description}
        nameError={nameError}
        descriptionRows={2}
        onNameChange={setName}
        onDescriptionChange={setDescription}
      />
      {saveFailed && (
        <p role="alert" className="text-sm text-error-600">
          {t("edit.failed")}
        </p>
      )}
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onClose} disabled={saving}>
          {t("cancel")}
        </Button>
        <Button type="submit" loading={saving} disabled={!name.trim() || !changed}>
          {t("edit.save")}
        </Button>
      </DialogFooter>
    </form>
  );
}
