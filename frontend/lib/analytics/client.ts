import { api, bearer, call } from "@/lib/api";
import { LOGIN_ACTIVITY_DAYS } from "@/lib/analytics/constants";
import type { LoginActivityPoint } from "@/lib/analytics/types";

export async function fetchLoginActivity(
  token: string,
  { days = LOGIN_ACTIVITY_DAYS }: { days?: number } = {},
): Promise<LoginActivityPoint[]> {
  return call<LoginActivityPoint[]>(() =>
    api.GET("/api/v1/analytics/login-activity", {
      params: { query: { days } },
      headers: bearer(token),
    }),
  );
}
