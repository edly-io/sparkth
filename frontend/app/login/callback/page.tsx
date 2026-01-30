"use client";

import { Suspense, useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { setAuthTokens } from "@/lib/auth-context";
import { SparkthLogo } from "@/components/SparkthLogo";
import Link from "next/link";

function LoadingSpinner() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-white py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full text-center">
        <div className="flex justify-center mb-8">
          <SparkthLogo />
        </div>
        <div className="flex items-center justify-center gap-3">
          <svg
            className="animate-spin h-5 w-5 text-primary-600"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          <p className="text-edly-gray-600">Completing sign in...</p>
        </div>
      </div>
    </div>
  );
}

function ErrorDisplay({ message }: { message: string }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-white py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full text-center">
        <div className="flex justify-center mb-8">
          <SparkthLogo />
        </div>
        <div className="rounded-md bg-edly-red-50 p-4 mb-6">
          <p className="text-sm text-edly-red-700">{message}</p>
        </div>
        <Link
          href="/login"
          className="text-primary-600 hover:text-primary-700 font-medium"
        >
          Return to login
        </Link>
      </div>
    </div>
  );
}

function CallbackHandler() {
  const searchParams = useSearchParams();
  const processedRef = useRef(false);

  const token = searchParams.get("token");
  const expiresAt = searchParams.get("expires_at");
  const errorParam = searchParams.get("error");

  useEffect(() => {
    if (processedRef.current) return;
    if (errorParam || !token || !expiresAt) return;

    processedRef.current = true;
    setAuthTokens(token, expiresAt);
    window.location.href = "/";
  }, [token, expiresAt, errorParam]);

  if (errorParam) {
    return <ErrorDisplay message={decodeURIComponent(errorParam)} />;
  }

  if (!token || !expiresAt) {
    return <ErrorDisplay message="Authentication failed. Missing token information." />;
  }

  return <LoadingSpinner />;
}

export default function GoogleCallbackPage() {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <CallbackHandler />
    </Suspense>
  );
}
