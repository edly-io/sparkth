"use client";

import { useEffect, useState } from "react";
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
import { Select } from "@/core/components/ui/Select";
import { Spinner } from "@/core/components/ui/Spinner";
import { PermissionPicker } from "@/core/permissions/components/ui/PermissionPicker";
import { RoleDetailsFields } from "@/core/permissions/components/ui/RoleDetailsFields";
import { usePermissionList } from "@/core/permissions/hooks";
import { formatRoleName } from "@/core/permissions/roleDisplay";
import { toggleItem } from "@/core/permissions/sets";
import type { RoleCreate, RoleResponse } from "@/core/permissions/types";

/** Where the new role's first permissions come from. */
type PermissionSource = "none" | "duplicate" | "choose";

/**
 * Asks for a new role's name and description, trimmed, the description `null` when left empty, and
 * what it starts from: no permissions, a duplicate of one of `roles`, with that role's permissions,
 * or permissions chosen from the full list, loaded when that is first selected. Calls `onCreate`
 * with all of it, closes once the role is created, and stays open with a message when the name is
 * taken or creating fails.
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
  const t = useTranslations("permissions.roles");
  const { token } = useAuth();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [permissionSource, setPermissionSource] = useState<PermissionSource>("none");
  const [selectedRoleId, setSelectedRoleId] = useState<number>();
  // The role to duplicate: the one selected, or the first listed until one is selected (the roles
  // may only arrive after the dialog opens).
  const duplicateRoleId = selectedRoleId ?? roles[0]?.id;
  const [chosen, setChosen] = useState<ReadonlySet<string>>(new Set());
  const { permissionList, load: loadPermissionList } = usePermissionList(token);
  const [nameError, setNameError] = useState<string>();
  const [createFailed, setCreateFailed] = useState(false);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (permissionSource === "choose") loadPermissionList();
  }, [permissionSource, loadPermissionList]);

  const getPermissionsToGrant = (): string[] | undefined => {
    switch (permissionSource) {
      case "none":
        return undefined;
      case "duplicate": {
        const duplicateRole = roles.find((role) => role.id === duplicateRoleId);
        if (!duplicateRole) {
          throw new Error(`The role to duplicate, ${duplicateRoleId}, is not listed`);
        }
        return duplicateRole.permissions;
      }
      case "choose":
        if (permissionList.status !== "loaded") throw new Error("The permissions are not loaded");
        return permissionList.permissions
          .map((permission) => permission.name)
          .filter((permission) => chosen.has(permission));
    }
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setCreating(true);
    setNameError(undefined);
    setCreateFailed(false);
    try {
      const permissions = getPermissionsToGrant();
      await onCreate({
        name: name.trim(),
        description: description.trim() || null,
        ...(permissions && { permissions }),
      });
      onClose();
    } catch (error) {
      if (error instanceof ApiRequestError && error.status === 409) {
        setNameError(t("form.nameTaken"));
      } else {
        console.error("Creating the role failed:", error);
        setCreateFailed(true);
      }
      setCreating(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <RoleDetailsFields
        name={name}
        description={description}
        nameError={nameError}
        descriptionRows={1}
        onNameChange={setName}
        onDescriptionChange={setDescription}
      />
      <fieldset className="space-y-2">
        <legend className="mb-1.5 text-sm font-medium text-foreground">
          {t("create.startFrom.label")}
        </legend>
        <PermissionSourceOption
          label={t("create.startFrom.none")}
          selected={permissionSource === "none"}
          onSelect={() => setPermissionSource("none")}
        />
        {roles.length > 0 && (
          <PermissionSourceOption
            label={t("create.startFrom.duplicate")}
            selected={permissionSource === "duplicate"}
            onSelect={() => setPermissionSource("duplicate")}
          >
            <div className="w-40 shrink-0">
              <Select
                aria-label={t("create.startFrom.duplicateSource")}
                value={String(duplicateRoleId)}
                onChange={(event) => setSelectedRoleId(Number(event.target.value))}
                disabled={permissionSource !== "duplicate"}
                options={roles.map((role) => ({
                  value: String(role.id),
                  label: formatRoleName(role.name),
                }))}
                className="border py-1.5 pl-3 text-sm"
              />
            </div>
          </PermissionSourceOption>
        )}
        <PermissionSourceOption
          label={t("create.startFrom.choose")}
          selected={permissionSource === "choose"}
          onSelect={() => setPermissionSource("choose")}
        />
        {permissionSource === "choose" && permissionList.status === "loading" && (
          <div
            role="status"
            aria-label={t("create.permissionsLoading")}
            className="flex justify-center py-2"
          >
            <Spinner size="md" />
          </div>
        )}
        {permissionSource === "choose" && permissionList.status === "failed" && (
          <p role="alert" className="text-sm text-error-600">
            {t("create.permissionsFailed")}
          </p>
        )}
        {permissionSource === "choose" && permissionList.status === "loaded" && (
          <PermissionPicker
            permissions={permissionList.permissions}
            chosen={chosen}
            onToggle={(permission) => setChosen(toggleItem(chosen, permission))}
          />
        )}
      </fieldset>
      {createFailed && (
        <p role="alert" className="text-sm text-error-600">
          {t("create.failed")}
        </p>
      )}
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onClose} disabled={creating}>
          {t("cancel")}
        </Button>
        <Button
          type="submit"
          loading={creating}
          disabled={
            !name.trim() || (permissionSource === "choose" && permissionList.status !== "loaded")
          }
        >
          {t("create.submit")}
        </Button>
      </DialogFooter>
    </form>
  );
}

/**
 * One place the new role's first permissions can come from, as a radio row; `children` sit at its
 * end, such as the role to duplicate.
 */
function PermissionSourceOption({
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
