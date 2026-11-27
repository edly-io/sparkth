"use client";

import { useTranslations } from "next-intl";
import { Input } from "@/core/components/ui/Input";
import { Textarea } from "@/core/components/ui/Textarea";

/**
 * The name and description inputs of a role's form, each as long as a role allows. `nameError`
 * shows under the name, and the description is `descriptionRows` lines tall.
 */
export function RoleDetailsFields({
  name,
  description,
  nameError,
  descriptionRows,
  onNameChange,
  onDescriptionChange,
}: {
  name: string;
  description: string;
  nameError: string | undefined;
  descriptionRows: number;
  onNameChange: (name: string) => void;
  onDescriptionChange: (description: string) => void;
}) {
  const t = useTranslations("permissions.roles.form");
  return (
    <>
      <Input
        id="role-name"
        label={t("name")}
        value={name}
        maxLength={50}
        error={nameError}
        onChange={(event) => onNameChange(event.target.value)}
        autoFocus
      />
      <Textarea
        id="role-description"
        label={t("description")}
        value={description}
        maxLength={255}
        rows={descriptionRows}
        onChange={(event) => onDescriptionChange(event.target.value)}
      />
    </>
  );
}
