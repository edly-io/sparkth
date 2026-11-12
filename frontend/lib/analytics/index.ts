/**
 * What a plugin's analytics code may use from core's analytics: the ISO date type, the chart
 * bucket sizes, and the helper that fills a bucketed series for a chart.
 */
export { type IsoDate } from "@/core/analytics/dates";
export { buildSeries, type Bucket, type BucketCount } from "@/core/analytics/series";
