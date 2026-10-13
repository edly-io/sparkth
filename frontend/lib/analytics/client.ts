import { api, bearer, call } from "@/lib/api";
import type { IsoDate } from "@/lib/analytics/dates";
import type { ChatActivityPoint, LoginsPoint } from "@/lib/analytics/types";

// Day buckets: the page rolls them up itself, so changing the bucket doesn't refetch.
export async function fetchLogins(
  token: string,
  { from, to }: { from: IsoDate; to: IsoDate },
): Promise<LoginsPoint[]> {
  return call<LoginsPoint[]>(() =>
    api.GET("/api/v1/analytics/logins", {
      params: { query: { from, to, bucket: "day" } },
      headers: bearer(token),
    }),
  );
}

export async function fetchChatActivity(
  token: string,
  { from, to }: { from: IsoDate; to: IsoDate },
): Promise<ChatActivityPoint[]> {
  return call<ChatActivityPoint[]>(() =>
    api.GET("/api/v1/chat/analytics/activity", {
      params: { query: { from, to, bucket: "day" } },
      headers: bearer(token),
    }),
  );
}
