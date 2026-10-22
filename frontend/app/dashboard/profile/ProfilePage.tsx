"use client";

import { useState, type ReactNode, type SubmitEvent } from "react";
import { useTranslations } from "next-intl";
import { useAuth } from "@/lib/auth-context";
import { ApiRequestError, changePassword, updateCurrentUser, type CurrentUser } from "@/lib/api";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Spinner } from "@/components/Spinner";
import {
  emptyNewPassword,
  NewPasswordFields,
  useNewPasswordMismatch,
} from "@/components/NewPasswordFields";

/** Mirrors the backend's `user.name` limit. */
const NAME_MAX_LENGTH = 30;

/** The signed-in user's account details, with forms to edit their name and change their password. */
export default function ProfilePage() {
  const t = useTranslations("profile");
  const { user } = useAuth();

  if (!user) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="text-center">
          <Spinner className="mx-auto mb-4" />
          <p className="text-muted-foreground">{t("loading")}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background transition-colors">
      <div className="max-w-2xl px-4 py-4 sm:py-8 sm:px-6 lg:px-8 space-y-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground">{t("title")}</h1>
          <p className="mt-2 text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <AccountDetails user={user} />
        <NameForm name={user.name} />
        <PasswordSection hasPassword={user.has_password} />
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card variant="outlined" className="space-y-4">
      <h2 className="text-lg font-semibold text-foreground">{title}</h2>
      {children}
    </Card>
  );
}

function AccountDetails({ user }: { user: CurrentUser }) {
  const t = useTranslations("profile.details");
  const rows: [string, string][] = [
    [t("username"), user.username],
    [t("email"), user.email],
    [t("emailStatus"), user.email_verified ? t("verified") : t("unverified")],
    [t("signInMethod"), user.has_password ? t("methods.password") : t("methods.google")],
  ];

  return (
    <Section title={t("heading")}>
      <dl className="divide-y divide-border">
        {rows.map(([label, value]) => (
          <div key={label} className="grid grid-cols-1 sm:grid-cols-3 gap-1 py-2">
            <dt className="text-sm text-muted-foreground">{label}</dt>
            <dd className="text-sm text-foreground sm:col-span-2 break-all">{value}</dd>
          </div>
        ))}
      </dl>
    </Section>
  );
}

function NameForm({ name }: { name: string }) {
  const t = useTranslations("profile.name");
  const { token, refreshUser } = useAuth();
  const [value, setValue] = useState(name);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const trimmed = value.trim();
  const canSave = trimmed !== "" && trimmed !== name;

  const handleSubmit = async (e: SubmitEvent) => {
    e.preventDefault();
    if (!token || !canSave) return;
    setSaving(true);
    setError("");
    setSaved(false);
    try {
      await updateCurrentUser(token, { name: trimmed });
      setValue(trimmed);
      setSaved(true);
      await refreshUser();
    } catch (err) {
      setError(err instanceof ApiRequestError ? (err.fieldErrors.name ?? err.message) : t("error"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Section title={t("heading")}>
      {saved && <Alert severity="success">{t("saved")}</Alert>}
      <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3 sm:items-start">
        <div className="flex-1">
          <Input
            name="name"
            label={t("label")}
            value={value}
            maxLength={NAME_MAX_LENGTH}
            onChange={(e) => {
              setValue(e.target.value);
              setSaved(false);
              setError("");
            }}
            error={error}
          />
        </div>
        <Button
          type="submit"
          className="sm:mt-7"
          loading={saving}
          disabled={!canSave}
          spinnerLabel={t("saving")}
        >
          {t("save")}
        </Button>
      </form>
    </Section>
  );
}

const emptyPasswords = { current: "", ...emptyNewPassword };

function PasswordSection({ hasPassword }: { hasPassword: boolean }) {
  const t = useTranslations("profile.password");

  return (
    <Section title={t("heading")}>
      {hasPassword ? <PasswordForm /> : <p className="text-sm text-muted-foreground">{t("sso")}</p>}
    </Section>
  );
}

function PasswordForm() {
  const t = useTranslations("profile.password");
  const { token } = useAuth();
  const [values, setValues] = useState(emptyPasswords);
  const [errors, setErrors] = useState<Partial<typeof emptyPasswords> & { form?: string }>({});
  const [submitting, setSubmitting] = useState(false);
  const [changed, setChanged] = useState(false);
  const mismatch = useNewPasswordMismatch();

  const update = (field: keyof typeof emptyPasswords, value: string) => {
    setValues((v) => ({ ...v, [field]: value }));
    setChanged(false);
    setErrors((prev) => ({ ...prev, [field]: undefined, form: undefined }));
  };

  const handleSubmit = async (e: SubmitEvent) => {
    e.preventDefault();
    if (!token) return;
    setChanged(false);
    const mismatchError = mismatch(values);
    if (mismatchError) {
      setErrors({ confirm: mismatchError });
      return;
    }
    setSubmitting(true);
    setErrors({});
    try {
      await changePassword(token, {
        current_password: values.current,
        new_password: values.next,
      });
      setValues(emptyPasswords);
      setChanged(true);
    } catch (err) {
      if (!(err instanceof ApiRequestError)) {
        setErrors({ form: t("error") });
      } else if (err.status === 400) {
        setErrors({ current: err.message });
      } else if (err.fieldErrors.new_password) {
        setErrors({ next: err.fieldErrors.new_password });
      } else {
        setErrors({ form: err.message });
      }
    } finally {
      setSubmitting(false);
    }
  };

  const filled = values.current !== "" && values.next !== "" && values.confirm !== "";

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {changed && <Alert severity="success">{t("changed")}</Alert>}
      {errors.form && <Alert severity="error">{errors.form}</Alert>}
      <Input
        name="current_password"
        type="password"
        autoComplete="current-password"
        label={t("current")}
        value={values.current}
        onChange={(e) => update("current", e.target.value)}
        error={errors.current}
      />
      <NewPasswordFields values={values} errors={errors} onChange={update} />
      <Button type="submit" loading={submitting} disabled={!filled} spinnerLabel={t("submitting")}>
        {t("submit")}
      </Button>
    </form>
  );
}
