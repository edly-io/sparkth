import { ChartTable } from "@/components/ui/ChartTable";
import type { BarChartDatum } from "@/components/ui/BarChart";
import { cn } from "@/lib/utils";

interface RankedBarProps {
  data: BarChartDatum[];
  limit?: number;
  caption: string;
  headers: [string, string];
  formatValue?: (n: number) => string;
  className?: string;
}

// Top-N horizontal bars, largest first. HTML rather than SVG so long labels truncate
// and the layout reflows on narrow screens. The visual is hidden from assistive tech;
// the data is read from the ChartTable.
export function RankedBar({
  data,
  limit = 10,
  caption,
  headers,
  formatValue = String,
  className,
}: RankedBarProps) {
  const ranked = [...data].sort((a, b) => b.value - a.value).slice(0, limit);
  const max = Math.max(1, ...ranked.map((d) => d.value));

  return (
    <figure className={cn("space-y-2", className)}>
      <ol aria-hidden="true" className="space-y-2">
        {ranked.map((d, i) => (
          <li
            key={i}
            className="grid grid-cols-[minmax(0,10rem)_1fr_auto] items-center gap-3 text-sm"
          >
            <span className="truncate text-foreground" title={d.label}>
              {d.label}
            </span>
            <span className="h-2 rounded bg-surface-variant">
              <span
                data-bar
                className="block h-2 rounded bg-primary-500"
                style={{ width: `${(d.value / max) * 100}%` }}
              />
            </span>
            <span className="tabular-nums text-muted-foreground">{formatValue(d.value)}</span>
          </li>
        ))}
      </ol>
      <ChartTable
        caption={caption}
        headers={headers}
        rows={ranked.map((d) => [d.label, formatValue(d.value)])}
      />
    </figure>
  );
}
