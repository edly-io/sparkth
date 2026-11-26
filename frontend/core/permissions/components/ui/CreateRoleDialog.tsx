"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { twMerge } from "tailwind-merge";
import { ApiRequestError } from "@/lib/api";
import { useAuth } from "@/core/auth/hooks";
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
import { Select } from "@/core/components/ui/Select";
import { Textarea } from "@/core/components/ui/Textarea";
import { usePermissionList } from "@/core/permissions/hooks";
import { formatRoleName, getDeclaredPermissions } from "@/core/permissions/roleDisplay";
import type { RoleCreate, RoleResponse } from "@/core/permissions/types";

type StartFrom = "none" | "copy";

/**
 * Asks for a new role's name and description, trimmed, the description `null` when left empty, and
 * what it starts from: no permissions, or a copy of one of `roles`. A copy takes only the permissions
 * still declared, loaded once when first needed. Calls `onCreate` with all of it, closes once
 * the role is created, and stays open with a message when the name is taken or creating fails.
 */
export function CreateRoleDialog({
  open,
  roles,
  onCreate,
  onClose,
}: {
  open: boolean;
  roles: RoleResponse[];
  onCreate: (role: RoleCreate) => Promise<void>;
  onClose: () => void;
}) {
  const t = useTranslations("permissions.roles.create");
  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="sm:max-w-lg md:max-w-lg lg:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t("title")}</DialogTitle>
          <DialogDescription>{t("intro")}</DialogDescription>
        </DialogHeader>
        {/* Mounted per opening, so the form starts empty each time. */}
        <RoleForm roles={roles} onCreate={onCreate} onClose={onClose} />
      </DialogContent>
    </Dialog>
  );
}

function RoleForm({
  roles,
  onCreate,
  onClose,
}: {
  roles: RoleResponse[];
  onCreate: (role: RoleCreate) => Promise<void>;
  onClose: () => void;
}) {
  const t = useTranslations("permissions.roles.create");
  const { token } = useAuth();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [startFrom, setStartFrom] = useState<StartFrom>("none");
  const [roleToCopyId, setRoleToCopyId] = useState(roles[0]?.id);
  const { permissionList, load: loadPermissionList } = usePermissionList(token);
  const [nameError, setNameError] = useState<string>();
  const [failed, setFailed] = useState(false);
  const [creating, setCreating] = useState(false);

  const selectStartFrom = (option: StartFrom) => {
    setStartFrom(option);
    if (option !== "none") loadPermissionList();
  };

  const getPermissionsToGrant = (): string[] | undefined => {
    if (startFrom === "none" || permissionList.status !== "loaded") return undefined;
    const roleToCopy = roles.find((role) => role.id === roleToCopyId);
    return getDeclaredPermissions(roleToCopy?.permissions ?? [], permissionList.permissions);
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setCreating(true);
    setNameError(undefined);
    setFailed(false);
    const permissions = getPermissionsToGrant();
    try {
      await onCreate({
        name: name.trim(),
        description: description.trim() || null,
        ...(permissions && { permissions }),
      });
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
        rows={1}
        onChange={(event) => setDescription(event.target.value)}
      />
      <fieldset className="space-y-2">
        <legend className="mb-1.5 text-sm font-medium text-foreground">
          {t("startFrom.label")}
        </legend>
        <StartOption
          label={t("startFrom.none")}
          selected={startFrom === "none"}
          onSelect={() => selectStartFrom("none")}
        />
        {roles.length > 0 && (
          <StartOption
            label={t("startFrom.copy")}
            selected={startFrom === "copy"}
            onSelect={() => selectStartFrom("copy")}
          >
            <div className="w-40 shrink-0">
              <Select
                aria-label={t("startFrom.copySource")}
                value={String(roleToCopyId)}
                onChange={(event) => setRoleToCopyId(Number(event.target.value))}
                disabled={startFrom !== "copy"}
                options={roles.map((role) => ({
                  value: String(role.id),
                  label: formatRoleName(role.name),
                }))}
                className="border py-1.5 pl-3 text-sm"
              />
            </div>
          </StartOption>
        )}
        {startFrom !== "none" && permissionList.status === "failed" && (
          <p role="alert" className="text-sm text-error-600">
            {t("permissionsFailed")}
          </p>
        )}
      </fieldset>
      {failed && (
        <p role="alert" className="text-sm text-error-600">
          {t("failed")}
        </p>
      )}
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onClose} disabled={creating}>
          {t("cancel")}
        </Button>
        <Button
          type="submit"
          loading={creating}
          disabled={!name.trim() || (startFrom !== "none" && permissionList.status !== "loaded")}
        >
          {t("submit")}
        </Button>
      </DialogFooter>
    </form>
  );
}

/** One way to start the new role, as a radio row; `children` sit at its end, such as the role to copy. */
function StartOption({
  label,
  selected,
  onSelect,
  children,
}: {
  label: string;
  selected: boolean;
  onSelect: () => void;
  children?: React.ReactNode;
}) {
  return (
    <div
      className={twMerge(
        "flex items-center justify-between gap-3 rounded-lg border px-3.5 py-2.5",
        selected ? "border-primary-500 bg-primary-50 dark:bg-primary-500/10" : "border-border",
      )}
    >
      <label className="flex items-center gap-2.5 whitespace-nowrap text-sm text-foreground">
        <input
          type="radio"
          name="start-from"
          className="h-4 w-4 accent-primary-600"
          checked={selected}
          onChange={onSelect}
        />
        {label}
      </label>
      {children}
    </div>
  );
}
