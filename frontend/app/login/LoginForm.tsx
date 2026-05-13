"use client";

import { useState, type SubmitEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "@tanstack/react-form";
import { login as loginApi, getGoogleLoginUrl, ApiRequestError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { SparkthLogo } from "@/components/SparkthLogo";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Alert } from "@/components/ui/Alert";
import { Card } from "@/components/ui/Card";
import { ThemeToggle } from "@/components/ThemeToggle";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();

  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [googleLoading, setGoogleLoading] = useState(false);

  const searchParams = useSearchParams();
  const oauthError = searchParams.get("error");

  const form = useForm({
    defaultValues: { username: "", password: "" },
    onSubmit: async ({ value }) => {
      setError("");
      setFieldErrors({});

      try {
        const response = await loginApi(value);
        login(response.access_token, response.expires_at);
        router.push("/");
      } catch (err) {
        if (err instanceof ApiRequestError) {
          setError(err.message);
          setFieldErrors(err.fieldErrors);
        } else {
          setError("An unexpected error occurred. Please try again.");
        }
      }
    },
  });

  const handleFormSubmit = (e: SubmitEvent<HTMLFormElement>) => {
    e.preventDefault();
    form.handleSubmit();
  };

  const handleGoogleLogin = async () => {
    setError("");
    setGoogleLoading(true);

    try {
      const response = await getGoogleLoginUrl();
      window.location.href = response.url;
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setError(err.message);
      } else {
        setError("Failed to initiate Google login. Please try again.");
      }
      setGoogleLoading(false);
    }
  };

  return (
    <div className="min-h-dvh flex items-center justify-center bg-background py-6 px-4 sm:py-12 sm:px-6 lg:px-8 transition-colors">
      <Card variant="elevated" className="max-w-md w-full p-4 sm:p-6 relative">
        <div className="absolute top-3 right-3 sm:top-4 sm:right-4">
          <ThemeToggle />
        </div>
        <div className="flex justify-center mb-6">
          <SparkthLogo size={56} />
        </div>

        <h2 className="text-center text-2xl sm:text-3xl font-bold text-foreground mb-2">Log in</h2>
        <p className="text-center text-sm sm:text-base text-muted-foreground mb-6 sm:mb-8">
          Welcome Back! Please enter your details
        </p>

        <form className="space-y-4 sm:space-y-6" onSubmit={handleFormSubmit}>
          {oauthError === "email_not_whitelisted" && (
            <Alert severity="error">
              Your email is not authorized to register. Contact an administrator.
            </Alert>
          )}
          {error && <Alert severity="error">{error}</Alert>}

          <form.Field name="username">
            {(field) => (
              <Input
                name="username"
                type="text"
                required
                placeholder="Username"
                value={field.state.value}
                onBlur={field.handleBlur}
                onChange={(e) => field.handleChange(e.target.value)}
                error={fieldErrors.username}
              />
            )}
          </form.Field>

          <form.Field name="password">
            {(field) => (
              <Input
                name="password"
                type="password"
                required
                placeholder="Password"
                value={field.state.value}
                onBlur={field.handleBlur}
                onChange={(e) => field.handleChange(e.target.value)}
                error={fieldErrors.password}
              />
            )}
          </form.Field>

          <div className="flex justify-end">
            <Link
              href="/forgot-password"
              className="text-sm font-medium text-foreground hover:text-muted-foreground transition-colors"
            >
              Forgot Password?
            </Link>
          </div>

          <form.Subscribe selector={(state) => state.isSubmitting}>
            {(isSubmitting) => (
              <Button
                type="submit"
                loading={isSubmitting}
                disabled={googleLoading}
                spinnerLabel="Signing In"
                fullWidth
                size="lg"
              >
                Sign In
              </Button>
            )}
          </form.Subscribe>
        </form>

        <div className="mt-6">
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-border" />
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-2 bg-card text-muted-foreground">Or continue with</span>
            </div>
          </div>

          <form.Subscribe selector={(state) => state.isSubmitting}>
            {(isSubmitting) => (
              <Button
                type="button"
                variant="outline"
                onClick={handleGoogleLogin}
                loading={googleLoading}
                disabled={isSubmitting}
                spinnerLabel="Redirecting"
                fullWidth
                size="lg"
                className="mt-4"
              >
                <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24">
                  <path
                    fill="#4285F4"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                  />
                </svg>
                Sign in with Google
              </Button>
            )}
          </form.Subscribe>
        </div>

        <p className="mt-6 text-center text-sm text-muted-foreground">
          Don&apos;t have an account?{" "}
          <Link
            href="/register"
            className="font-medium text-primary-500 hover:text-primary-700 transition-colors"
          >
            Sign up
          </Link>
        </p>
      </Card>
    </div>
  );
}
