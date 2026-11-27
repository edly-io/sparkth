import { api, bearer, call, type Schema } from "@/lib/api";

export type ActivitySummary = Schema<"ActivitySummary">;
/** The level an activity launches at: as a learner (`play`) or as its author (`edit`). */
export type LaunchPermission = "play" | "edit";

export async function listActivities(
  token: string,
  signal?: AbortSignal,
): Promise<ActivitySummary[]> {
  return call<ActivitySummary[]>(() =>
    api.GET("/api/v1/pxc/activities", { headers: bearer(token), signal }),
  );
}

// Mints a fresh launch for the activity under `permission` and returns the URL to iframe.
export async function getActivityEmbedUrl(
  token: string,
  activityId: string,
  permission: LaunchPermission,
  signal?: AbortSignal,
): Promise<string> {
  const launch = await call<Schema<"ActivityLaunch">>(() =>
    api.GET("/api/v1/pxc/activities/{activity_id}/launch", {
      params: { path: { activity_id: activityId }, query: { permission } },
      headers: bearer(token),
      signal,
    }),
  );
  return launch.embed_url;
}

/** Permanently deletes an activity; rejects with `ApiRequestError` (404 if unknown, 403 if not permitted). */
export async function deleteActivity(token: string, activityId: string): Promise<void> {
  await call(() =>
    api.DELETE("/api/v1/pxc/activities/{activity_id}", {
      params: { path: { activity_id: activityId } },
      headers: bearer(token),
    }),
  );
}
