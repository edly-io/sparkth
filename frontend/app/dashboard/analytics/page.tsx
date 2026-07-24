import type { Metadata } from "next";
import { LOGIN_ACTIVITY_DAYS } from "@/lib/analytics";
import AnalyticsPage from "./AnalyticsPage";

export const metadata: Metadata = {
  title: "Analytics | Sparkth",
  description: `Login activity over the last ${LOGIN_ACTIVITY_DAYS} days`,
};

export default function Page() {
  return <AnalyticsPage />;
}
