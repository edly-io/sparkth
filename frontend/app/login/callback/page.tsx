"use client";

import { Suspense, useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { setAuthTokens } from "@/lib/auth-context";
import { SparkthLogo } from "@/components/SparkthLogo";
import { Loader2 } from "lucide-react";
import Link from "next/link";

function LoadingSpinner() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full text-center">
        <div className="flex justify-center mb-8">
          <SparkthLogo />
        </div>
        <div className="flex items-center justify-center gap-3">
          <Loader2 className="h-5 w-5 animate-spin text-primary-500" />
          <p className="text-muted-foreground">Completing sign in...</p>
        </div>
      </div>
    </div>
  );
}

function ErrorDisplay({ message }: { message: string }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full text-center">
        <div className="flex justify-center mb-8">
          <SparkthLogo />
        </div>
        <div className="rounded-md bg-red-50 dark:bg-red-900/20 p-4 mb-6">
          <p className="text-sm text-red-700 dark:text-red-400">{message}</p>
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
    return (
      <ErrorDisplay message="Authentication failed. Missing token information." />
    );
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
