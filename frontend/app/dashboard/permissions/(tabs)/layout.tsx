import { PermissionsHeading } from "@/core/permissions/components/layout/PermissionsHeading";
import { PermissionsNav } from "@/core/permissions/components/ui/PermissionsNav";
import { PERMISSIONS_TABS } from "../tabs";

/** The Access & permissions tabs' frame: the section heading and the tab bar above the open tab. */
export default function TabsLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <PermissionsHeading />
      <PermissionsNav tabs={PERMISSIONS_TABS} />
      {children}
    </>
  );
}
