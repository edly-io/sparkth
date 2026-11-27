import type { Metadata } from "next";
import ComparePage from "./ComparePage";

export const metadata: Metadata = {
  title: "Compare permissions · Access & permissions | Sparkth",
  description: "The roles' permissions side by side",
};

export default function Page() {
  return <ComparePage />;
}
