"use client";

import { useState, type SubmitEvent } from "react";
import { useTranslations } from "next-intl";

import { AuthCard, AuthHeading, AuthLink } from "@/components/AuthCard";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/core/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { ApiRequestError, requestPasswordReset } from "@/lib/api";

/**
 * Asks for the account's email and requests a reset link for it. The confirmation reads the
 * same whether or not the email has an account, matching the API, which never says.
 */
export default function ForgotPasswordForm() {
  const t = useTranslations("passwordReset.forgot");
  const [email, setEmail] = useState("");
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: SubmitEvent) => {
    e.preventDefault();
    const trimmed = email.trim();
    if (!trimmed) return;
    setSubmitting(true);
    setError("");
    try {
      await requestPasswordReset(trimmed);
      setSentTo(trimmed);
    } catch (err) {
      setError(
        err instanceof ApiRequestError && err.status === 429 ? t("rateLimited") : t("error"),
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (sentTo) {
    return (
      <AuthCard>
        <AuthHeading title={t("sentTitle")} subtitle={t("sent", { email: sentTo })} />
        <AuthLink href="/login">{t("back")}</AuthLink>
      </AuthCard>
    );
  }

  return (
    <AuthCard>
      <AuthHeading title={t("title")} subtitle={t("subtitle")} />
      {error && <Alert severity="error">{error}</Alert>}
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          name="email"
          type="email"
          autoComplete="email"
          required
          label={t("email")}
          placeholder="you@example.com"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            setError("");
          }}
        />
        <Button
          type="submit"
          loading={submitting}
          disabled={!email.trim()}
          spinnerLabel={t("submitting")}
          fullWidth
          size="lg"
        >
          {t("submit")}
        </Button>
      </form>
      <AuthLink href="/login">{t("back")}</AuthLink>
    </AuthCard>
  );
}
