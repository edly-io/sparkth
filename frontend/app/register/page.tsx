"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { register as registerApi, ApiRequestError } from "@/lib/api";
import { SparkthLogo } from "@/components/SparkthLogo";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Alert } from "@/components/ui/Alert";
import { Card } from "@/components/ui/Card";

export default function RegisterPage() {
  const router = useRouter();
  const [formData, setFormData] = useState({
    name: "",
    username: "",
    email: "",
    password: "",
    confirmPassword: "",
  });
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setFieldErrors({});

    if (formData.password !== formData.confirmPassword) {
      setFieldErrors({ confirmPassword: "Passwords do not match" });
      return;
    }

    setLoading(true);

    try {
      await registerApi({
        name: formData.name,
        username: formData.username,
        email: formData.email,
        password: formData.password,
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
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background py-12 px-4 sm:px-6 lg:px-8 transition-colors">
      <Card variant="elevated" className="max-w-md w-full">
        <div className="flex justify-center mb-1">
          <SparkthLogo size={96} />
        </div>

        <h2 className="text-center text-3xl font-bold text-foreground mb-2">
          Create your account
        </h2>
        <p className="text-center text-base text-muted-foreground mb-8">
          Already have an account?{" "}
          <Link
            href="/login"
            className="font-medium text-primary-500 hover:text-primary-700 transition-colors"
          >
            Sign in
          </Link>
        </p>

        <form className="space-y-5" onSubmit={handleSubmit}>
          {success && (
            <Alert severity="success">
              Account created successfully! Redirecting to login...
            </Alert>
          )}
          {error && <Alert severity="error">{error}</Alert>}

          <Input
            name="name"
            type="text"
            required
            placeholder="Full name"
            value={formData.name}
            onChange={handleChange}
            error={fieldErrors.name}
          />

          <Input
            name="username"
            type="text"
            required
            placeholder="Username"
            value={formData.username}
            onChange={handleChange}
            error={fieldErrors.username}
          />

          <Input
            name="email"
            type="email"
            required
            placeholder="Email"
            value={formData.email}
            onChange={handleChange}
            error={fieldErrors.email}
          />

          <Input
            name="password"
            type="password"
            required
            placeholder="Enter your password"
            value={formData.password}
            onChange={handleChange}
            error={fieldErrors.password}
          />

          <Input
            name="confirmPassword"
            type="password"
            required
            placeholder="Confirm password"
            value={formData.confirmPassword}
            onChange={handleChange}
            error={fieldErrors.confirmPassword}
          />

          <Button
            type="submit"
            loading={loading}
            disabled={success}
            fullWidth
            size="lg"
            spinnerLabel="Saving"
          >
            {success ? "Account created!" : "Create account"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
