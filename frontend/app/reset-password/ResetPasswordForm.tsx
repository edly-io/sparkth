"use client";

import { useState, type SubmitEvent } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";

import { AuthCard, AuthHeading, AuthLink } from "@/components/AuthCard";
import {
  emptyNewPassword,
  NewPasswordFields,
  useNewPasswordMismatch,
  type NewPasswordValues,
} from "@/components/NewPasswordFields";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { ApiRequestError, confirmPasswordReset } from "@/lib/api";

/**
 * Sets a new password with the token from an emailed reset link (`?token=`). A link the API
 * refuses (unknown, used or expired) replaces the form with the API's reason and a way to
 * request a new link.
 */
export default function ResetPasswordForm() {
  const t = useTranslations("passwordReset.reset");
  const token = useSearchParams().get("token");
  const mismatch = useNewPasswordMismatch();
  const [values, setValues] = useState<NewPasswordValues>(emptyNewPassword);
  const [errors, setErrors] = useState<Partial<NewPasswordValues> & { form?: string }>({});
  const [refusedLink, setRefusedLink] = useState<string | null>(token ? null : t("missingToken"));
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const update = (field: keyof NewPasswordValues, value: string) => {
    setValues((v) => ({ ...v, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: undefined, form: undefined }));
  };

  const handleSubmit = async (e: SubmitEvent) => {
    e.preventDefault();
    if (!token) return;
    const mismatchError = mismatch(values);
    if (mismatchError) {
      setErrors({ confirm: mismatchError });
      return;
    }
    setSubmitting(true);
    setErrors({});
    try {
      await confirmPasswordReset({ token, new_password: values.next });
      setDone(true);
    } catch (err) {
      if (!(err instanceof ApiRequestError)) {
        setErrors({ form: t("error") });
      } else if (err.status === 400) {
        setRefusedLink(err.message);
      } else if (err.fieldErrors.new_password) {
        setErrors({ next: err.fieldErrors.new_password });
      } else {
        setErrors({ form: err.message });
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (done) {
    return (
      <AuthCard>
        <AuthHeading title={t("doneTitle")} subtitle={t("done")} />
        <AuthLink href="/login">{t("signIn")}</AuthLink>
      </AuthCard>
    );
  }

  if (refusedLink) {
    return (
      <AuthCard>
        <AuthHeading title={t("invalidTitle")} subtitle={refusedLink} />
        <AuthLink href="/forgot-password">{t("requestNew")}</AuthLink>
      </AuthCard>
    );
  }

  const filled = values.next !== "" && values.confirm !== "";

  return (
    <AuthCard>
      <AuthHeading title={t("title")} subtitle={t("subtitle")} />
      {errors.form && <Alert severity="error">{errors.form}</Alert>}
      <form onSubmit={handleSubmit} className="space-y-4">
        <NewPasswordFields values={values} errors={errors} onChange={update} />
        <Button
          type="submit"
          loading={submitting}
          disabled={!filled}
          spinnerLabel={t("submitting")}
          fullWidth
          size="lg"
        >
          {t("submit")}
        </Button>
      </form>
    </AuthCard>
  );
}
