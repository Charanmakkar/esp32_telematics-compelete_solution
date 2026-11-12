import {
  Brush,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { localTime, numeric } from "../services/format";
import { EmptyState } from "../components/EmptyState";

export const channelColors = [
  "#22D3EE",
  "#8B9CFF",
  "#2DD4A1",
  "#F5BA5A",
  "#E18BFF",
  "#56A7FF",
  "#F17B9D",
  "#A6D96A",
  "#BCA8FF",
  "#F79C67",
];
export type PlotPoint = { timestamp_ms: number; [key: string]: number | null };
export function TelemetryChart({
  data,
  channels = [1],
  height = 300,
  brush = false,
  compact = false,
}: {
  data: PlotPoint[];
  channels?: number[];
  height?: number;
  brush?: boolean;
  compact?: boolean;
}) {
  if (
    !data.length ||
    !data.some((point) =>
      channels.some(
        (channel) =>
          point[`analog_${channel}`] !== null &&
          point[`analog_${channel}`] !== undefined,
      ),
    )
  ) {
    return compact ? (
      <div className="empty-spark">
        <span />
        Awaiting signal
      </div>
    ) : (
      <div style={{ height }}>
        <EmptyState title="No valid measurements in this range">
          Measurements appear here after telemetry is received and the channel
          validity flag is set.
        </EmptyState>
      </div>
    );
  }
  return (
    <div
      className={compact ? "sparkline-container" : "telemetry-chart"}
      style={{ height }}
      aria-label={compact ? "Channel trend" : "Analog telemetry time series"}
    >
      <ResponsiveContainer width="100%" height="100%" minWidth={0}>
        <LineChart
          data={data}
          margin={
            compact
              ? { top: 4, right: 1, bottom: 4, left: 1 }
              : { top: 12, right: 16, left: -13, bottom: 0 }
          }
        >
          {!compact && (
            <CartesianGrid
              vertical={false}
              stroke="var(--grid-line)"
              strokeDasharray="3 5"
            />
          )}
          {!compact && (
            <XAxis
              dataKey="timestamp_ms"
              type="number"
              domain={["dataMin", "dataMax"]}
              tickFormatter={(value) => localTime(value)}
              tick={{ fill: "var(--text-muted)", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              minTickGap={55}
            />
          )}
          {!compact && (
            <YAxis
              tick={{ fill: "var(--text-muted)", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(value) => `${value}`}
              width={65}
            />
          )}
          {!compact && (
            <Tooltip
              labelFormatter={(value) =>
                new Date(Number(value)).toLocaleString()
              }
              formatter={(value: unknown, name: unknown) => [
                `${numeric(typeof value === "number" ? value : null, 1)} mV`,
                String(name),
              ]}
              contentStyle={{
                background: "var(--surface-raised)",
                border: "1px solid var(--border-strong)",
                borderRadius: 10,
                color: "var(--text-primary)",
                fontSize: 12,
              }}
              cursor={{ stroke: "var(--text-muted)", strokeDasharray: "3 3" }}
            />
          )}
          {channels.map((channel) => (
            <Line
              key={channel}
              type="monotone"
              dataKey={`analog_${channel}`}
              name={`Analog ${String(channel).padStart(2, "0")}`}
              stroke={channelColors[channel - 1]}
              strokeWidth={compact ? 1.8 : 2}
              dot={false}
              activeDot={
                compact
                  ? false
                  : { r: 4, strokeWidth: 3, stroke: "var(--surface)" }
              }
              isAnimationActive={false}
              connectNulls={false}
            />
          ))}
          {brush && (
            <Brush
              dataKey="timestamp_ms"
              height={30}
              stroke="var(--border-strong)"
              fill="var(--surface-muted)"
              tickFormatter={(value) => localTime(value)}
              travellerWidth={8}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
