"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import SparkthHeader from "@/components/SparkthHeader";
import { SparkthLogo } from "@/components/SparkthLogo";

export default function Home() {
  const { isAuthenticated, logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isAuthenticated) {
      router.push("/dashboard");
    }
  }, [isAuthenticated, router]);

  if (isAuthenticated) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background transition-colors">
      <SparkthHeader isAuthenticated={false} logout={logout} />

      <main className="max-w-7xl mx-auto py-16 sm:py-24 px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <div className="flex justify-center mb-8">
            <SparkthLogo size={120} />
          </div>

          <h1 className="text-3xl font-extrabold text-foreground sm:text-4xl md:text-5xl lg:text-6xl">
            Welcome to <span className="text-primary-500">Sparkth</span>
          </h1>

          <p className="mt-4 max-w-md mx-auto text-base text-muted-foreground sm:text-lg md:mt-6 md:text-xl md:max-w-2xl">
            Your AI-powered platform for creating engaging educational content.
            Transform your resources into courses with ease.
          </p>

          <div className="mt-10 flex flex-col sm:flex-row justify-center gap-4 px-4 sm:px-0">
            <Link
              href="/register"
              className="inline-flex items-center justify-center px-8 py-3 min-h-[48px] border border-transparent text-base font-semibold rounded-lg text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 transition-colors shadow-sm"
            >
              Get Started
            </Link>
            <Link
              href="/login"
              className="inline-flex items-center justify-center px-8 py-3 min-h-[48px] border border-border text-base font-semibold rounded-lg text-foreground bg-card hover:bg-surface-variant focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 transition-colors"
            >
              Sign in
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}
