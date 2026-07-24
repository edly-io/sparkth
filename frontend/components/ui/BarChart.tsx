import { SVGAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils";

export interface BarChartDatum {
  label: string;
  value: number;
}

interface BarChartProps extends SVGAttributes<SVGSVGElement> {
  data: BarChartDatum[];
}

// Internal viewBox coordinate space (not pixels). The SVG scales to its
// container via `w-full h-auto`, preserving this 3:1 aspect ratio.
const VIEW_W = 600;
const VIEW_H = 200;
const PAD_X = 8; // left/right inset so edge bars aren't flush to the frame
const PAD_TOP = 8; // headroom above the tallest bar
const PAD_BOTTOM = 20; // room for the x-axis labels
const GAP_RATIO = 0.2; // fraction of each slot left as inter-bar gap

// A themed, accessible bar chart in the shadcn style — pure SVG, zero
// dependencies. Bars, gridline, and labels colour from theme CSS variables via
// Tailwind utilities, so it renders correctly in light and dark mode.
export const BarChart = forwardRef<SVGSVGElement, BarChartProps>(
  ({ data, className, ...props }, ref) => {
    const max = Math.max(1, ...data.map((d) => d.value));
    const plotW = VIEW_W - PAD_X * 2;
    const plotH = VIEW_H - PAD_TOP - PAD_BOTTOM;
    const slot = data.length > 0 ? plotW / data.length : plotW;
    const barW = slot * (1 - GAP_RATIO);
    const total = data.reduce((sum, d) => sum + d.value, 0);

    return (
      <svg
        ref={ref}
        role="img"
        aria-label={`Bar chart of ${data.length} data points totalling ${total}`}
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        className={cn("w-full h-auto text-primary-500", className)}
        {...props}
      >
        {/* max-value gridline */}
        <line
          x1={PAD_X}
          y1={PAD_TOP}
          x2={VIEW_W - PAD_X}
          y2={PAD_TOP}
          className="stroke-border"
          strokeWidth={1}
        />
        {data.map((d, i) => {
          const barH = (d.value / max) * plotH;
          const x = PAD_X + i * slot + (slot - barW) / 2;
          const y = PAD_TOP + (plotH - barH);
          return (
            <rect
              key={d.label}
              x={x}
              y={y}
              width={barW}
              height={barH}
              rx={2}
              className="fill-current"
            >
              {/* native tooltip — no JS tooltip machinery */}
              <title>{`${d.label}: ${d.value}`}</title>
            </rect>
          );
        })}
        {data.length > 0 && (
          <text
            x={PAD_X}
            y={VIEW_H - 6}
            textAnchor="start"
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
    );
  },
);

BarChart.displayName = "BarChart";
