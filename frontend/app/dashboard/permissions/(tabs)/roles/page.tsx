import type { Metadata } from "next";
import RolesPage from "./RolesPage";

export const metadata: Metadata = {
  title: "Roles · Access & permissions | Sparkth",
  description: "The roles you can see",
};

export default function Page() {
  return <RolesPage />;
}
