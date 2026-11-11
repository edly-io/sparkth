import { api, bearer, call, type Schema } from "@/lib/api";

/** An entry on the registration email whitelist: one address or one domain. */
export type WhitelistEntry = Schema<"WhitelistedEmailResponse">;

/** Every entry on the registration whitelist. */
export async function getWhitelist(token: string): Promise<WhitelistEntry[]> {
  return call<WhitelistEntry[]>(() => api.GET("/api/v1/whitelist/", { headers: bearer(token) }));
}

/** Adds an address or a domain (`@example.com`) to the registration whitelist. */
export async function addWhitelistEntry(token: string, value: string): Promise<WhitelistEntry> {
  return call<WhitelistEntry>(() =>
    api.POST("/api/v1/whitelist/", { body: { value }, headers: bearer(token) }),
  );
}

/** Removes a whitelist entry by its id. */
export async function removeWhitelistEntry(token: string, id: number): Promise<void> {
  return call<void>(() =>
    api.DELETE("/api/v1/whitelist/{entry_id}", {
      params: { path: { entry_id: id } },
      headers: bearer(token),
    }),
  );
}
