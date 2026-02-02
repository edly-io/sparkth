"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { login as loginApi, ApiRequestError } from "@/lib/api";
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
  const [formData, setFormData] = useState({
    username: "",
    password: "",
  });
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

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
    setLoading(true);

    try {
      const response = await loginApi(formData);
      login(response.access_token, response.expires_at);
      router.push("/");
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
    <div className="min-h-screen flex items-center justify-center bg-background py-12 px-4 sm:px-6 lg:px-8 transition-colors relative">
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>
      <Card variant="elevated" className="max-w-md w-full p-4 sm:p-6">
        <div className="flex justify-center mb-1">
          <SparkthLogo size={96}/>
        </div>

        <h2 className="text-center text-3xl font-bold text-foreground mb-2">
          Log in
        </h2>
        <p className="text-center text-base text-muted-foreground mb-8">
          Welcome Back! Please enter your details
        </p>

        <form className="space-y-6" onSubmit={handleSubmit}>
          {error && <Alert severity="error">{error}</Alert>}

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
            name="password"
            type="password"
            required
            placeholder="Password"
            value={formData.password}
            onChange={handleChange}
            error={fieldErrors.password}
          />

          <div className="flex justify-end">
            <Link
              href="/forgot-password"
              className="text-sm font-medium text-foreground hover:text-muted-foreground transition-colors"
            >
              Forgot Password?
            </Link>
          </div>

          <Button
            type="submit"
            loading={loading}
            spinnerLabel="Signing In"
            fullWidth
            size="lg"
          >
            Sign In
          </Button>
        </form>

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
