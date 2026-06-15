import { type Schema } from "@/lib/api";

export type ConnectionStatus = Schema<"SlackConnectionStatusResponse">;
export type AuthorizationUrlResponse = Schema<"SlackAuthorizationUrlResponse">;
export type BotResponseLogItem = Schema<"BotResponseLogItem">;
export type ConnectionLogItem = Schema<"ConnectionLogItem">;
export type LogItem = BotResponseLogItem | ConnectionLogItem;
export type LogsResponse = Schema<"LogsResponse">;
export type RagSourcesResponse = Schema<"RagSourcesResponse">;

export interface FetchLogsOptions {
  limit?: number;
  cursor?: string;
  sinceId?: number;
}
