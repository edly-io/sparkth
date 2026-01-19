"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { register as registerApi, ApiRequestError } from "@/lib/api";
import { SparkthLogo } from "@/components/SparkthLogo";

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
    <div className="min-h-screen flex items-center justify-center bg-white">
      <div className="max-w-md w-full">
        <div className="flex justify-center">
          <SparkthLogo />
        </div>

        <div>
          <h2 className="text-center text-3xl font-bold text-edly-gray-900 mb-2">
            Create your account
          </h2>
          <p className="text-center text-base text-edly-gray-600 mb-8">
            Already have an account?{" "}
            <Link
              href="/login"
              className="font-medium text-primary hover:text-primary-600"
            >
              Sign in
            </Link>
          </p>

          <form className="space-y-5" onSubmit={handleSubmit}>
            {success && (
              <div className="rounded-md bg-primary-50 p-4">
                <p className="text-sm text-primary-700">
                  Account created successfully! Redirecting to login...
                </p>
              </div>
            )}
            {error && (
              <div className="rounded-md bg-edly-red-50 p-4">
                <p className="text-sm text-edly-red-700">{error}</p>
              </div>
            )}

            <div>
              <label
                htmlFor="name"
                className="block text-sm font-medium text-edly-gray-700 mb-2"
              >
                Full Name
              </label>
              <input
                id="name"
                name="name"
                type="text"
                required
                className={`appearance-none block w-full px-4 py-3 border rounded-lg placeholder-gray-400 text-edly-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent ${
                  fieldErrors.name
                    ? "border-edly-red-500"
                    : "border-edly-gray-300"
                }`}
                placeholder="John Doe"
                value={formData.name}
                onChange={handleChange}
              />
              {fieldErrors.name && (
                <p className="mt-1 text-sm text-edly-red-600">
                  {fieldErrors.name}
                </p>
              )}
            </div>

            <div>
              <label
                htmlFor="username"
                className="block text-sm font-medium text-edly-gray-700 mb-2"
              >
                Username
              </label>
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
                placeholder="johndoe"
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
              <label
                htmlFor="email"
                className="block text-sm font-medium text-edly-gray-700 mb-2"
              >
                Email address
              </label>
              <input
                id="email"
                name="email"
                type="email"
                required
                className={`appearance-none block w-full px-4 py-3 border rounded-lg placeholder-gray-400 text-edly-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent ${
                  fieldErrors.email
                    ? "border-edly-red-500"
                    : "border-edly-gray-300"
                }`}
                placeholder="john@example.com"
                value={formData.email}
                onChange={handleChange}
              />
              {fieldErrors.email && (
                <p className="mt-1 text-sm text-edly-red-600">
                  {fieldErrors.email}
                </p>
              )}
            </div>

            <div>
              <label
                htmlFor="password"
                className="block text-sm font-medium text-edly-gray-700 mb-2"
              >
                Password
              </label>
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
                placeholder="Enter your password"
                value={formData.password}
                onChange={handleChange}
              />
              {fieldErrors.password && (
                <p className="mt-1 text-sm text-edly-red-600">
                  {fieldErrors.password}
                </p>
              )}
            </div>

            <div>
              <label
                htmlFor="confirmPassword"
                className="block text-sm font-medium text-edly-gray-700 mb-2"
              >
                Confirm Password
              </label>
              <input
                id="confirmPassword"
                name="confirmPassword"
                type="password"
                required
                className={`appearance-none block w-full px-4 py-3 border rounded-lg placeholder-gray-400 text-edly-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent ${
                  fieldErrors.confirmPassword
                    ? "border-edly-red-500"
                    : "border-edly-gray-300"
                }`}
                placeholder="Confirm your password"
                value={formData.confirmPassword}
                onChange={handleChange}
              />
              {fieldErrors.confirmPassword && (
                <p className="mt-1 text-sm text-edly-red-600">
                  {fieldErrors.confirmPassword}
                </p>
              )}
            </div>

            <button
              type="submit"
              disabled={loading || success}
              className="w-full flex justify-center py-3 px-4 border border-transparent text-base font-semibold rounded-lg text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading
                ? "Creating account..."
                : success
                ? "Account created!"
                : "Create account"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
