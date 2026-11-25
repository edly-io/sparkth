import type { Metadata } from "next";
import GroupsPage from "./GroupsPage";

export const metadata: Metadata = {
  title: "Groups · Access & permissions | Sparkth",
  description: "The groups you can see",
};

export default function Page() {
  return <GroupsPage />;
}
