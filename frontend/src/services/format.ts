import type { Telemetry } from "./types";

export const channelName = (n: number) =>
  `Analog ${String(n).padStart(2, "0")}`;
export const channelKey = (n: number) => `analog_${n}` as const;
export const sampleTime = (sample: Telemetry | null | undefined) =>
  sample
    ? sample.time_valid && sample.timestamp_ms !== null
      ? sample.timestamp_ms
      : Date.parse(sample.received_at || "") || null
    : null;
export function localTime(
  value: string | number | null | undefined,
  seconds = true,
) {
  if (value === undefined || value === null || value === "") return "—";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "—";
  return date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    ...(seconds ? { second: "2-digit" } : {}),
  });
}
export function dateTime(value: string | number | null | undefined) {
  if (value === undefined || value === null || value === "")
    return "Not received";
  const date = new Date(value);
  return Number.isFinite(date.getTime())
    ? date.toLocaleString()
    : "Not received";
}
export function age(
  value: string | number | null | undefined,
  now = Date.now(),
) {
  if (value === undefined || value === null || value === "") return "No data";
  const ms = new Date(value).getTime();
  if (!Number.isFinite(ms)) return "No data";
  const seconds = Math.max(0, Math.floor((now - ms) / 1000));
  if (seconds < 1) return "Just now";
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
}
export const numeric = (value: number | null | undefined, digits = 0) =>
  value === undefined || value === null || !Number.isFinite(value)
    ? "—"
    : value.toLocaleString(undefined, {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      });
export const isFresh = (sample: Telemetry | null, now = Date.now()) =>
  !!sample &&
  !sample.stale &&
  sample.received_at !== undefined &&
  now - Date.parse(sample.received_at) < 5000;
