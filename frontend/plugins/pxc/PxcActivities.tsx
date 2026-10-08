"use client";

import { useSearchParams } from "next/navigation";
import { ActivityList } from "@/plugins/pxc/components/ActivityList";
import { ActivityPreview } from "@/plugins/pxc/components/ActivityPreview";

// The `/dashboard/pxc` page: the list, or one activity's preview when `?activity=<id>` is set.
// `&as=edit` opens the preview in the Author view.
export default function PxcActivities(): React.JSX.Element {
  const params = useSearchParams();
  const activityId = params.get("activity");
  if (!activityId) return <ActivityList />;
  const permission = params.get("as") === "edit" ? "edit" : "play";
  return <ActivityPreview key={activityId} activityId={activityId} permission={permission} />;
}
