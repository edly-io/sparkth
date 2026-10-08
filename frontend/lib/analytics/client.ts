import { api, bearer, call } from "@/lib/api";
import type { LoginActivityPoint } from "@/lib/analytics/types";

export async function fetchLoginActivity(
  token: string,
  { days }: { days: number },
): Promise<LoginActivityPoint[]> {
  return call<LoginActivityPoint[]>(() =>
    api.GET("/api/v1/analytics/login-activity", {
      params: { query: { days } },
      headers: bearer(token),
    }),
  );
}
