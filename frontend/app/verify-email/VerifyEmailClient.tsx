"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { SparkthLogo } from "@/components/SparkthLogo";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { ApiRequestError, resendVerificationEmail, verifyEmail } from "@/lib/api";

type Status = "loading" | "success" | "expired" | "invalid";

export default function VerifyEmailClient() {
  // Suspense boundary co-located with useSearchParams: required by Next.js
  // App Router so only this subtree (not the whole page) bails out to client
  // rendering. The parent page.tsx wraps this too — nesting is harmless.
  return (
    <Suspense fallback={null}>
      <VerifyEmailContent />
    </Suspense>
  );
}

function VerifyEmailContent() {
  const { push, replace } = useRouter();
  const { get } = useSearchParams();
  const token = get("token");

  const [status, setStatus] = useState<Status>("loading");
  const [resendEmail, setResendEmail] = useState("");
  const [resendStatus, setResendStatus] = useState<
    "idle" | "sending" | "sent" | "rate_limited" | "error"
  >("idle");

  useEffect(() => {
    if (!token) {
      replace("/login");
      return;
    }
    let cancelled = false;
    (async () => {
      let next: Status;
      try {
        await verifyEmail(token);
        next = "success";
      } catch (err) {
        next =
          err instanceof ApiRequestError && err.message === "expired_token" ? "expired" : "invalid";
      }
      if (!cancelled) setStatus(next);
    })();
    return () => {
      cancelled = true;
    };
  }, [token, replace]);

  const handleResend = async () => {
    if (!resendEmail) return;
    setResendStatus("sending");
    try {
      await resendVerificationEmail(resendEmail);
      setResendStatus("sent");
    } catch (err) {
      if (err instanceof ApiRequestError && err.status === 429) {
        setResendStatus("rate_limited");
      } else {
        setResendStatus("error");
      }
    }
  };

  const resendButtonLabel = (() => {
    switch (resendStatus) {
      case "sending":
        return "Sending…";
      case "sent":
        return "Email sent — check your inbox";
      case "rate_limited":
        return "Please wait before resending";
      case "error":
        return "Try again";
      default:
        return "Send new link";
    }
  })();

  return (
    <div className="min-h-dvh flex items-center justify-center bg-background py-6 px-4 sm:py-12 sm:px-6 lg:px-8 transition-colors">
      <Card variant="elevated" className="max-w-md w-full p-4 sm:p-6 relative">
        <div className="absolute top-3 right-3 sm:top-4 sm:right-4">
          <ThemeToggle />
        </div>
        <div className="flex justify-center mb-1">
          <SparkthLogo size={72} />
        </div>

        {status === "loading" && (
          <div className="text-center py-6">
            <p className="text-base text-muted-foreground">Verifying your email…</p>
          </div>
        )}

        {status === "success" && (
          <div className="text-center space-y-4 py-2">
            <h2 className="text-2xl sm:text-3xl font-bold text-foreground">Email confirmed</h2>
            <p className="text-sm sm:text-base text-muted-foreground">
              You can now sign in to your Sparkth account.
            </p>
            <Button onClick={() => push("/login")} fullWidth size="lg">
              Go to login
            </Button>
          </div>
        )}

        {(status === "expired" || status === "invalid") && (
          <div className="space-y-4 py-2">
            <h2 className="text-center text-2xl sm:text-3xl font-bold text-foreground">
              {status === "expired" ? "Link expired" : "Invalid link"}
            </h2>
            <p className="text-center text-sm sm:text-base text-muted-foreground">
              Enter your email below and we&apos;ll send a new confirmation link.
            </p>
            {resendStatus === "error" && (
              <Alert severity="error">
                We couldn&apos;t send the email right now. Please try again in a moment.
              </Alert>
            )}
            <Input
              name="email"
              type="email"
              required
              placeholder="you@example.com"
              value={resendEmail}
              onChange={(e) => setResendEmail(e.target.value)}
            />
            <Button
              onClick={handleResend}
              disabled={!resendEmail || resendStatus === "sending" || resendStatus === "sent"}
              fullWidth
              size="lg"
            >
              {resendButtonLabel}
            </Button>
            <p className="text-center text-sm">
              <Link
                href="/login"
                className="font-medium text-primary-500 hover:text-primary-700 transition-colors"
              >
                Back to sign in
              </Link>
            </p>
          </div>
        )}
      </Card>
    </div>
  );
}
