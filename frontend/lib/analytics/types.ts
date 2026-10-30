import type { Schema } from "@/lib/api";

export type LoginsPoint = Schema<"LoginsPoint">;
export type ChatActivityPoint = Schema<"ChatActivityPoint">;
export type SummaryCount = Schema<"SummaryCount">;
export type DriveDocumentsPoint = Schema<"DriveDocumentsPoint">;
export type EventCatalogEntry = Schema<"EventCatalogEntry">;
export type ExploreResult = Schema<"ExploreResult">;
/** A saved Explore view; `config` is an `ExploreConfig` as it was saved. */
export type AnalyticsView = Schema<"AnalyticsViewOut">;
