import { api, bearer, call } from "@/lib/api";
import type { IsoDate } from "@/lib/analytics/dates";
import type { LoginsPoint } from "@/lib/analytics/types";

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
