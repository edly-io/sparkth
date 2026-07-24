import { api, bearer, rethrowOrWrapConnectionError } from "@/lib/api";
import type { LoginActivityPoint } from "@/lib/analytics/types";

export async function fetchLoginActivity(
  token: string,
  { days = 30 }: { days?: number } = {},
): Promise<LoginActivityPoint[]> {
  try {
    const { data } = await api.GET("/api/v1/analytics/login-activity", {
      params: { query: { days } },
      headers: bearer(token),
    });
    return data as LoginActivityPoint[];
  } catch (error) {
    rethrowOrWrapConnectionError(error);
  }
}
