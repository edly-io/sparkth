"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "@tanstack/react-form";
import { register as registerApi, ApiRequestError } from "@/lib/api";
import { SparkthLogo } from "@/components/SparkthLogo";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Alert } from "@/components/ui/Alert";
import { Card } from "@/components/ui/Card";
import { ThemeToggle } from "@/components/ThemeToggle";

export default function RegisterPage() {
  const router = useRouter();

  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [success, setSuccess] = useState(false);

  const form = useForm({
    defaultValues: {
      name: "",
      username: "",
      email: "",
      password: "",
      confirmPassword: "",
    },
    onSubmit: async ({ value }) => {
      if (value.password !== value.confirmPassword) {
        setFieldErrors({ confirmPassword: "Passwords do not match" });
        return;
      }

      setError("");
      setFieldErrors({});

      try {
        await registerApi({
          name: value.name,
          username: value.username,
          email: value.email,
          password: value.password,
        });
        setSuccess(true);
        setTimeout(() => {
          router.push("/login");
        }, 2000);
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

  const handleFormSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    form.handleSubmit();
  };

  return (
    <div className="min-h-dvh flex items-center justify-center bg-background py-6 px-4 sm:py-12 sm:px-6 lg:px-8 transition-colors">
      <Card variant="elevated" className="max-w-md w-full p-4 sm:p-6 relative">
        <div className="absolute top-3 right-3 sm:top-4 sm:right-4">
          <ThemeToggle />
        </div>
        <div className="flex justify-center mb-1">
          <SparkthLogo size={72} />
        </div>

        <h2 className="text-center text-2xl sm:text-3xl font-bold text-foreground mb-2">
          Create your account
        </h2>
        <p className="text-center text-sm sm:text-base text-muted-foreground mb-6 sm:mb-8">
          Already have an account?{" "}
          <Link
            href="/login"
            className="font-medium text-primary-500 hover:text-primary-700 transition-colors"
          >
            Sign in
          </Link>
        </p>

        <form className="space-y-4 sm:space-y-5" onSubmit={handleFormSubmit}>
          {success && (
            <Alert severity="success">Account created successfully! Redirecting to login...</Alert>
          )}
          {error && <Alert severity="error">{error}</Alert>}

          <form.Field name="name">
            {(field) => (
              <Input
                name="name"
                type="text"
                required
                placeholder="Full name"
                value={field.state.value}
                onBlur={field.handleBlur}
                onChange={(e) => field.handleChange(e.target.value)}
                error={fieldErrors.name}
              />
            )}
          </form.Field>

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

          <form.Field name="email">
            {(field) => (
              <Input
                name="email"
                type="email"
                required
                placeholder="Email"
                value={field.state.value}
                onBlur={field.handleBlur}
                onChange={(e) => field.handleChange(e.target.value)}
                error={fieldErrors.email}
              />
            )}
          </form.Field>

          <form.Field name="password">
            {(field) => (
              <Input
                name="password"
                type="password"
                required
                placeholder="Enter your password"
                value={field.state.value}
                onBlur={field.handleBlur}
                onChange={(e) => field.handleChange(e.target.value)}
                error={fieldErrors.password}
              />
            )}
          </form.Field>

          <form.Field name="confirmPassword">
            {(field) => (
              <Input
                name="confirmPassword"
                type="password"
                required
                placeholder="Confirm password"
                value={field.state.value}
                onBlur={field.handleBlur}
                onChange={(e) => field.handleChange(e.target.value)}
                error={fieldErrors.confirmPassword}
              />
            )}
          </form.Field>

          <form.Subscribe selector={(state) => state.isSubmitting}>
            {(isSubmitting) => (
              <Button
                type="submit"
                loading={isSubmitting}
                disabled={success}
                fullWidth
                size="lg"
                spinnerLabel="Saving"
              >
                {success ? "Account created!" : "Create account"}
              </Button>
            )}
          </form.Subscribe>
        </form>
      </Card>
    </div>
  );
}
