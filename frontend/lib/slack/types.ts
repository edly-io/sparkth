import { type Schema } from "@/lib/api";

export type ConnectionStatus = Schema<"app__core_plugins__slack__types__ConnectionStatusResponse">;
export type AuthorizationUrlResponse =
  Schema<"app__core_plugins__slack__types__AuthorizationUrlResponse">;
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
