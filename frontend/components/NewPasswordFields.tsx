"use client";

import { useTranslations } from "next-intl";
import { Input } from "@/components/ui/Input";

/** The two values a new-password form collects: the password and its confirmation. */
export type NewPasswordValues = { next: string; confirm: string };

/** An empty pair of new-password values, to start or reset a form with. */
export const emptyNewPassword: NewPasswordValues = { next: "", confirm: "" };

/**
 * The "new password" and "confirm new password" inputs, with the complexity hint, shared by
 * the profile page's password change and the reset-password page. The parent owns the values
 * and errors, and checks that the two match with `useNewPasswordMismatch` before submitting.
 */
export function NewPasswordFields({
  values,
  errors,
  onChange,
}: {
  values: NewPasswordValues;
  errors: Partial<NewPasswordValues>;
  onChange: (field: keyof NewPasswordValues, value: string) => void;
}) {
  const t = useTranslations("newPassword");

  return (
    <>
      <Input
        name="new_password"
        type="password"
        autoComplete="new-password"
        label={t("label")}
        value={values.next}
        onChange={(e) => onChange("next", e.target.value)}
        error={errors.next}
        helperText={t("hint")}
      />
      <Input
        name="confirm_password"
        type="password"
        autoComplete="new-password"
        label={t("confirm")}
        value={values.confirm}
        onChange={(e) => onChange("confirm", e.target.value)}
        error={errors.confirm}
      />
    </>
  );
}

/** The translated mismatch message for `NewPasswordFields`, or `undefined` when the values match. */
export function useNewPasswordMismatch() {
  const t = useTranslations("newPassword");
  return (values: NewPasswordValues) =>
    values.next === values.confirm ? undefined : t("mismatch");
}
