import type { Metadata } from "next";
import AnalyticsPage from "./AnalyticsPage";

export const metadata: Metadata = {
  title: "Analytics | Sparkth",
  description: "Login activity over the last 30 days",
};

export default function Page() {
  return <AnalyticsPage />;
}
