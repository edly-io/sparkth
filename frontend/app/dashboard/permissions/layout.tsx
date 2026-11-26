"use client";

import { useAuth } from "@/core/auth/hooks";
import { usePermissionChecks } from "@/lib/permissions/hooks";
import { PERMISSIONS_SECTION_CHECKS } from "@/core/permissions/section";
import { PermissionsShell } from "@/core/permissions/components/layout/PermissionsShell";
import { PermissionsNav } from "@/core/permissions/components/ui/PermissionsNav";
import { Forbidden } from "@/core/components/layout/Forbidden";
import { Spinner } from "@/core/components/ui/Spinner";
import { PERMISSIONS_TABS } from "./tabs";

/**
 * The Access & permissions section's frame. It opens only when every section check passes, and
 * shows the "no access" page when any is refused or the check fails, so every tab's URL is gated.
 */
export default function PermissionsLayout({ children }: { children: React.ReactNode }) {
  const { token } = useAuth();
  const answers = usePermissionChecks(token, PERMISSIONS_SECTION_CHECKS);
  const denied = answers.includes("denied");
  const allowed = answers.every((answer) => answer === "allowed");

  return (
    <PermissionsShell>
      {denied && <Forbidden />}
      {allowed && (
        <>
          <PermissionsNav tabs={PERMISSIONS_TABS} />
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
