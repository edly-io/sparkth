"use client";

import { useSearchParams } from "next/navigation";
import { ActivityList } from "@/plugins/pxc/components/ActivityList";
import { ActivityPreview } from "@/plugins/pxc/components/ActivityPreview";

// The `/dashboard/pxc` page: the list, or one activity's preview when `?activity=<id>` is set.
export default function PxcActivities(): React.JSX.Element {
  const activityId = useSearchParams().get("activity");
  if (activityId) return <ActivityPreview key={activityId} activityId={activityId} />;
  return <ActivityList />;
}
