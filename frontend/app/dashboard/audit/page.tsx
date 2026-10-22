import type { Metadata } from "next";
import AuditLogPage from "./AuditLogPage";

export const metadata: Metadata = {
  title: "Audit Log | Sparkth",
  description: "Review and export the audit trail",
};

export default function Page() {
  return <AuditLogPage />;
}
