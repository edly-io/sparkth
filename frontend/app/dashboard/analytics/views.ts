import { Compass, LayoutDashboard, LogIn, PenLine } from "lucide-react";

import { EXPLORE, type AnalyticsNavView } from "@/core/analytics/components/layout/AnalyticsNav";

/**
 * The analytics views, in rail order. A view read from a plugin's route names that plugin, and
 * its entry shows while that plugin is installed.
 */
export const ANALYTICS_VIEWS = [
  { key: "overview", href: "/dashboard/analytics", icon: LayoutDashboard },
  { key: "logins", href: "/dashboard/analytics/logins", icon: LogIn },
  { key: "authoring", href: "/dashboard/analytics/authoring", icon: PenLine, plugin: "compose" },
  { key: "explore", href: EXPLORE, icon: Compass },
] as const satisfies readonly AnalyticsNavView[];
