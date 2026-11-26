"use client";

import { usePathname } from "next/navigation";
import { useAuth } from "@/core/auth/hooks";
import { usePermissionChecks } from "@/core/permissions/hooks";
import { PERMISSIONS_SECTION_CHECKS } from "@/core/permissions/section";
import { PermissionsShell } from "@/core/permissions/components/layout/PermissionsShell";
import { PermissionsNav } from "@/core/permissions/components/ui/PermissionsNav";
import { Forbidden } from "@/core/components/layout/Forbidden";
import { Spinner } from "@/core/components/ui/Spinner";
import { PERMISSIONS_TABS } from "./tabs";

/**
 * The Access & permissions section's frame. It opens only when every section check passes, and
 * shows the "no access" page when any is refused or the check fails, so every tab's URL is gated.
 * The section heading and tabs show on the tabs' own pages; a page below a tab, such as one role's,
 * has a heading and breadcrumb of its own.
 */
export default function PermissionsLayout({ children }: { children: React.ReactNode }) {
  const { token } = useAuth();
  const answers = usePermissionChecks(token, PERMISSIONS_SECTION_CHECKS);
  const denied = answers.includes("denied");
  const allowed = answers.every((answer) => answer === "allowed");
  const pathname = usePathname()?.replace(/\/$/, "") ?? "";
  const isTabPage = PERMISSIONS_TABS.some(({ href }) => href === pathname);

  return (
    <PermissionsShell withHeading={isTabPage}>
      {denied && <Forbidden />}
      {allowed && (
        <>
          {isTabPage && <PermissionsNav tabs={PERMISSIONS_TABS} />}
          {children}
        </>
      )}
      {!denied && !allowed && (
        <div className="flex justify-center py-24">
          <Spinner />
        </div>
      )}
    </PermissionsShell>
  );
}
