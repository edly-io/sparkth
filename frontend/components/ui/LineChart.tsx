import { ChartTable } from "@/components/ui/ChartTable";
import type { BarChartDatum } from "@/components/ui/BarChart";

const VIEW_W = 600;
const VIEW_H = 200;
const PAD_X = 8;
const PAD_TOP = 8;
const PAD_BOTTOM = 20;

interface LineChartProps {
  data: BarChartDatum[];
  comparison?: number[]; // previous period, aligned by index with `data`
  caption: string;
  headers: [string, string] | [string, string, string];
  formatValue?: (n: number) => string;
  className?: string;
}

// A trend line in the same plain-SVG style as BarChart, with an optional dashed
// previous-period line. Colours come from theme utilities for light and dark mode.
// The SVG is hidden from assistive tech; the data is read from the ChartTable.
export function LineChart({
  data,
  comparison: rawComparison,
  caption,
  headers,
  formatValue = String,
  className,
}: LineChartProps) {
  // Extra comparison values have no x slot; drop them so they can't skew the scale or overflow.
  const comparison = rawComparison?.slice(0, data.length);
  const plotW = VIEW_W - PAD_X * 2;
  const plotH = VIEW_H - PAD_TOP - PAD_BOTTOM;
  const max = Math.max(1, ...data.map((d) => d.value), ...(comparison ?? []));
  const x = (i: number) => (data.length > 1 ? PAD_X + (i * plotW) / (data.length - 1) : VIEW_W / 2);
  const y = (v: number) => PAD_TOP + plotH - (v / max) * plotH;
  const points = (values: number[]) => values.map((v, i) => `${x(i)},${y(v)}`).join(" ");

  return (
    <figure className={className}>
      <svg aria-hidden="true" viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} className="w-full h-auto">
        <line
          x1={PAD_X}
          y1={PAD_TOP + plotH}
          x2={VIEW_W - PAD_X}
          y2={PAD_TOP + plotH}
          className="stroke-border"
          strokeWidth={1}
        />
        {comparison && (
          <polyline
            points={points(comparison)}
            fill="none"
            strokeWidth={1.5}
            strokeDasharray="4 4"
            className="stroke-muted-foreground"
          />
        )}
        {data.length > 1 && (
          <polyline
            points={points(data.map((d) => d.value))}
            fill="none"
            strokeWidth={2}
            strokeLinejoin="round"
            className="stroke-primary-500"
          />
        )}
        {/* A one-vertex polyline paints nothing, so a lone point gets a dot. */}
        {data.length === 1 && (
          <circle cx={x(0)} cy={y(data[0].value)} r={3} className="fill-primary-500" />
        )}
        {data.length > 0 && (
          <text
            x={data.length === 1 ? x(0) : PAD_X}
            y={VIEW_H - 6}
            textAnchor={data.length === 1 ? "middle" : "start"}
            className="fill-muted-foreground text-[10px]"
          >
            {data[0].label}
          </text>
        )}
        {data.length > 1 && (
          <text
            x={VIEW_W - PAD_X}
            y={VIEW_H - 6}
            textAnchor="end"
            className="fill-muted-foreground text-[10px]"
          >
            {data[data.length - 1].label}
          </text>
        )}
      </svg>
      <ChartTable
        caption={caption}
        headers={headers}
        rows={data.map((d, i) =>
          comparison
            ? [
                d.label,
                formatValue(d.value),
                // A shorter previous period has no value here; "—", not a 0 that never happened.
                comparison[i] === undefined ? "—" : formatValue(comparison[i]),
              ]
            : [d.label, formatValue(d.value)],
        )}
      />
    </figure>
  );
}
