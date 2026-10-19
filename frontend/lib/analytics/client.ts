import { api, bearer, call } from "@/lib/api";
import type { IsoDate } from "@/lib/analytics/dates";
import type {
  ChatActivityPoint,
  DriveDocumentsPoint,
  LoginsPoint,
  SummaryCount,
} from "@/lib/analytics/types";

/** Logins per day for the range; the page rolls days up itself, so a bucket change doesn't refetch. */
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

/** Processed Drive documents per day and outcome, with summed seconds to final, for the period. */
export async function fetchDriveDocuments(
  token: string,
  { from, to }: { from: IsoDate; to: IsoDate },
): Promise<DriveDocumentsPoint[]> {
  return call<DriveDocumentsPoint[]>(() =>
    api.GET("/api/v1/google-drive/analytics/documents", {
      params: { query: { from, to, bucket: "day" } },
      headers: bearer(token),
    }),
  );
}

/** Every Overview figure, counted for the period and the one before it, in one request. */
export async function fetchSummary(
  token: string,
  { from, to }: { from: IsoDate; to: IsoDate },
): Promise<SummaryCount[]> {
  return call<SummaryCount[]>(() =>
    api.GET("/api/v1/analytics/summary", {
      params: { query: { from, to } },
      headers: bearer(token),
    }),
  );
}
