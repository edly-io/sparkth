"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { ApiRequestError } from "@/lib/api";
import { Button } from "@/core/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/core/components/ui/Dialog";
import { Input } from "@/core/components/ui/Input";
import { Textarea } from "@/core/components/ui/Textarea";
import type { RoleCreate } from "@/core/permissions/types";

/**
 * Asks for a new role's name and description and calls `onCreate` with them, trimmed, the
 * description `null` when left empty. Closes once the role is created; stays open with a message
 * when the name is taken or creating fails.
 */
export function CreateRoleDialog({
  open,
  onCreate,
  onClose,
}: {
  open: boolean;
  onCreate: (role: RoleCreate) => Promise<void>;
  onClose: () => void;
}) {
  const t = useTranslations("permissions.roles.create");
  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="sm:max-w-md md:max-w-md lg:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("title")}</DialogTitle>
          <DialogDescription>{t("intro")}</DialogDescription>
        </DialogHeader>
        {/* Mounted per opening, so the form starts empty each time. */}
        <RoleForm onCreate={onCreate} onClose={onClose} />
      </DialogContent>
    </Dialog>
  );
}

function RoleForm({
  onCreate,
  onClose,
}: {
  onCreate: (role: RoleCreate) => Promise<void>;
  onClose: () => void;
}) {
  const t = useTranslations("permissions.roles.create");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [nameError, setNameError] = useState<string>();
  const [failed, setFailed] = useState(false);
  const [creating, setCreating] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setCreating(true);
    setNameError(undefined);
    setFailed(false);
    try {
      await onCreate({ name: name.trim(), description: description.trim() || null });
      onClose();
    } catch (error) {
      if (error instanceof ApiRequestError && error.status === 409) {
        setNameError(t("nameTaken"));
      } else {
        console.error("Creating the role failed:", error);
        setFailed(true);
      }
      setCreating(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <Input
        id="role-name"
        label={t("name")}
        value={name}
        maxLength={50}
        error={nameError}
        onChange={(event) => setName(event.target.value)}
        autoFocus
      />
      <Textarea
        id="role-description"
        label={t("description")}
        value={description}
        maxLength={255}
        rows={2}
        onChange={(event) => setDescription(event.target.value)}
      />
      {failed && (
        <p role="alert" className="text-sm text-error-600">
          {t("failed")}
        </p>
      )}
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onClose} disabled={creating}>
          {t("cancel")}
        </Button>
        <Button type="submit" loading={creating} disabled={!name.trim()}>
          {t("submit")}
        </Button>
      </DialogFooter>
    </form>
  );
}
