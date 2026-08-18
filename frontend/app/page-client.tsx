"use client";

import Link from "next/link";
import { redirect } from "next/navigation";
import { useTranslations } from "next-intl";
import { useAuth } from "@/lib/auth-context";
import SparkthHeader from "@/components/SparkthHeader";
import { SparkthLogo } from "@/components/SparkthLogo";

export default function HomeClient() {
  const { isAuthenticated, logout } = useAuth();
  const t = useTranslations("home");

  if (isAuthenticated) {
    redirect("/dashboard");
  }

  return (
    <div className="min-h-screen bg-background transition-colors">
      <SparkthHeader isAuthenticated={false} logout={logout} />

      <main className="max-w-7xl mx-auto py-16 sm:py-24 px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <div className="flex justify-center mb-4">
            <SparkthLogo size={72} />
          </div>

          <h1 className="text-3xl font-extrabold text-foreground sm:text-4xl md:text-5xl lg:text-6xl">
            {t.rich("title", {
              brand: (chunks) => <span className="text-primary-500">{chunks}</span>,
            })}
          </h1>

          <p className="mt-4 max-w-md mx-auto text-base text-muted-foreground sm:text-lg md:mt-6 md:text-xl md:max-w-2xl">
            {t("tagline")}
          </p>

          <div className="mt-10 flex flex-col sm:flex-row justify-center gap-4 px-4 sm:px-0">
            <Link
              href="/register"
              className="inline-flex items-center justify-center px-8 py-3 min-h-[48px] border border-transparent text-base font-semibold rounded-lg text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 transition-colors shadow-sm"
            >
              {t("getStarted")}
            </Link>
            <Link
              href="/login"
              className="inline-flex items-center justify-center px-8 py-3 min-h-[48px] border border-border text-base font-semibold rounded-lg text-foreground bg-card hover:bg-surface-variant focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 transition-colors"
            >
              {t("signIn")}
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}
