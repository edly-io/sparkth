"use client";

import { useEffect, useState } from "react";
import { redirect } from "next/navigation";
import { ChartColumn } from "lucide-react";
import { useTranslations } from "next-intl";
import { useAuth } from "@/lib/auth-context";
import { checkPermission } from "@/lib/permissions";
import { Spinner } from "@/components/Spinner";
import { AnalyticsNav } from "./AnalyticsNav";

type Access = "checking" | "allowed" | "denied";

// Shell for every analytics view: the analytics.read gate (fails closed), the title and the rail.
export default function AnalyticsLayout({ children }: { children: React.ReactNode }) {
  const { token } = useAuth();
  const t = useTranslations("analytics");
  const [access, setAccess] = useState<Access>("checking");

  useEffect(() => {
    if (!token) return;
    let active = true;
    setAccess("checking");
    checkPermission(token, "analytics.read")
      .then((allowed) => {
        if (active) setAccess(allowed ? "allowed" : "denied");
      })
      .catch((error: unknown) => {
        console.error("Analytics permission check failed:", error);
        if (active) setAccess("denied");
      });
    return () => {
      active = false;
    };
  }, [token]);

  if (access === "denied") {
    redirect("/dashboard");
  }

  return (
    <div className="min-h-screen bg-background transition-colors">
      <div className="mx-auto px-4 py-4 sm:py-8 sm:px-6 lg:px-8">
        <div className="mb-6 flex items-center gap-3">
          <ChartColumn className="w-6 h-6 text-primary-500" aria-hidden="true" />
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground">{t("title")}</h1>
        </div>
        {access === "checking" ? (
          <div className="flex justify-center py-24">
            <Spinner />
          </div>
        ) : (
          <div className="flex flex-col gap-6 lg:flex-row">
            <AnalyticsNav />
            <div className="min-w-0 flex-1">{children}</div>
          </div>
        )}
      </div>
    </div>
  );
}
