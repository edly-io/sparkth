"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { login as loginApi, ApiRequestError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { SparkthLogo } from "@/components/SparkthLogo";

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
    <div className="min-h-screen flex items-center justify-center bg-white py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full">
        <div className="flex justify-center">
          <SparkthLogo />
        </div>

        <div>
          <h2 className="text-center text-3xl font-bold text-edly-gray-900 mb-2">
            Log in
          </h2>
          <p className="text-center text-base text-edly-gray-600 mb-8">
            Welcome Back! Please enter your details
          </p>

          <form className="space-y-6" onSubmit={handleSubmit}>
            {error && (
              <div className="rounded-md bg-edly-red-50 p-4">
                <p className="text-sm text-edly-red-700">{error}</p>
              </div>
            )}

            <div>
              <input
                id="username"
                name="username"
                type="text"
                required
                className={`appearance-none block w-full px-4 py-3 border rounded-lg placeholder-gray-400 text-edly-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent ${
                  fieldErrors.username
                    ? "border-edly-red-500"
                    : "border-edly-gray-300"
                }`}
                placeholder="Username"
                value={formData.username}
                onChange={handleChange}
              />
              {fieldErrors.username && (
                <p className="mt-1 text-sm text-edly-red-600">
                  {fieldErrors.username}
                </p>
              )}
            </div>

            <div>
              <input
                id="password"
                name="password"
                type="password"
                required
                className={`appearance-none block w-full px-4 py-3 border rounded-lg placeholder-gray-400 text-edly-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent ${
                  fieldErrors.password
                    ? "border-edly-red-500"
                    : "border-edly-gray-300"
                }`}
                placeholder="Password"
                value={formData.password}
                onChange={handleChange}
              />
              {fieldErrors.password && (
                <p className="mt-1 text-sm text-edly-red-600">
                  {fieldErrors.password}
                </p>
              )}
            </div>

            <div className="flex justify-end">
              <Link
                href="/forgot-password"
                className="text-sm font-medium text-edly-gray-900 hover:text-edly-gray-700"
              >
                Forgot Password?
              </Link>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex justify-center py-3 px-4 border border-transparent text-base font-semibold rounded-lg text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? "Signing in..." : "Sign In"}
            </button>
          </form>
          <p className="mt-6 text-center text-sm text-edly-gray-600">
            Don&apos;t have an account?{" "}
            <Link
              href="/register"
              className="font-medium text-primary-500 hover:text-primary-700"
            >
              Sign up
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
