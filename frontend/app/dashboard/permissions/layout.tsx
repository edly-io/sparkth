"use client";

import { useAuth } from "@/core/auth/hooks";
import { usePermissionChecks } from "@/core/permissions/hooks";
import { PERMISSIONS_SECTION_CHECKS } from "@/core/permissions/section";
import { PermissionsShell } from "@/core/permissions/components/layout/PermissionsShell";
import { Forbidden } from "@/core/components/layout/Forbidden";
import { Spinner } from "@/core/components/ui/Spinner";

/**
 * The Access & permissions section's frame. It opens only when every section check passes, and
 * shows the "no access" page when any is refused or the check fails, so every page's URL is gated.
 */
export default function PermissionsLayout({ children }: { children: React.ReactNode }) {
  const { token } = useAuth();
  const answers = usePermissionChecks(token, PERMISSIONS_SECTION_CHECKS);
  const denied = answers.includes("denied");
  const allowed = answers.every((answer) => answer === "allowed");

  return (
    <PermissionsShell>
      {denied && <Forbidden />}
      {allowed && children}
      {!denied && !allowed && (
        <div className="flex justify-center py-24">
          <Spinner />
        </div>
      )}
    </PermissionsShell>
  );
}
