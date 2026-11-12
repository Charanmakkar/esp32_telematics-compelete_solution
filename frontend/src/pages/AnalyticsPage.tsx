import { useEffect, useMemo, useState } from "react";
import {
  ArrowDownToLine,
  ArrowLeft,
  ChartNoAxesCombined,
  Clock3,
  Maximize2,
  RefreshCw,
  TriangleAlert,
} from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useTelemetry } from "../hooks/useTelemetry";
import { api } from "../services/api";
import {
  age,
  channelKey,
  channelName,
  dateTime,
  isFresh,
  numeric,
  sampleTime,
} from "../services/format";
import type { ChannelHistory } from "../services/types";
import { TelemetryChart, type PlotPoint } from "../charts/TelemetryChart";
import { StatusBadge } from "../components/StatusBadge";
import { CHANNEL_COUNT, channelMapping } from "../services/config";

const presets = [
  { label: "1 min", ms: 60000 },
  { label: "5 min", ms: 300000 },
  { label: "15 min", ms: 900000 },
  { label: "1 hour", ms: 3600000 },
  { label: "24 hours", ms: 86400000 },
];
function localInput(timestamp: number) {
  const date = new Date(timestamp);
  return new Date(timestamp - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}
export function AnalyticsPage() {
  const { channelId = "analog-1" } = useParams();
  const navigate = useNavigate();
  const channel = Number(channelId.replace("analog-", ""));
  const { deviceId, device, samples, received, now, connection } =
    useTelemetry();
  const [mode, setMode] = useState<"live" | "history">("live");
  const [range, setRange] = useState(300000);
  const [custom, setCustom] = useState(false);
  const [start, setStart] = useState(localInput(Date.now() - 3600000));
  const [end, setEnd] = useState(localInput(Date.now()));
  const [query, setQuery] = useState({
    start: Date.now() - 300000,
    end: Date.now(),
  });
  const [history, setHistory] = useState<ChannelHistory | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const key = channelKey(channel);
  useEffect(() => {
    if (mode !== "history" || channel < 1 || channel > CHANNEL_COUNT) return;
    const abort = new AbortController();
    setLoading(true);
    setError("");
    setHistory(null);
    api
      .history(deviceId, channel, query.start, query.end, abort.signal)
      .then(setHistory)
      .catch((err) => {
        if (!abort.signal.aborted)
          setError(
            err instanceof Error
              ? err.message
              : "Could not load historical measurements.",
          );
      })
      .finally(() => {
        if (!abort.signal.aborted) setLoading(false);
      });
    return () => abort.abort();
  }, [deviceId, channel, query, mode]);
  const liveData = useMemo<PlotPoint[]>(
    () =>
      (samples.length ? samples : received ? [received] : [])
        .filter((sample) => (sampleTime(sample) || 0) >= now - range)
        .map((sample) => ({
          timestamp_ms: sampleTime(sample) || now,
          [key]:
            sample.valid_mask & (1 << (channel - 1))
              ? sample.channels[key]
              : null,
        })),
    [samples, received, channel, key, range, now],
  );
  const data =
    mode === "history"
      ? (history?.points || []).map((point) => ({
          timestamp_ms: point.timestamp_ms,
          [key]: point.value,
        }))
      : liveData;
  const stats = useMemo(() => {
    if (mode === "history")
      return history?.stats || { min: null, max: null, avg: null, count: 0 };
    const values = liveData
      .map((point) => point[key])
      .filter(
        (value): value is number => value !== null && value !== undefined,
      );
    return {
      min: values.length ? Math.min(...values) : null,
      max: values.length ? Math.max(...values) : null,
      avg: values.length
        ? values.reduce((sum, n) => sum + n, 0) / values.length
        : null,
      count: values.length,
    };
  }, [history, mode, liveData, key]);
  if (channel < 1 || channel > CHANNEL_COUNT || !Number.isInteger(channel))
    return (
      <div className="panel not-found">
        <h1>Channel not found</h1>
        <p>Choose one of the six configured ADC1 channels.</p>
        <Link className="button primary" to="/">
          Back to overview
        </Link>
      </div>
    );
  function choosePreset(ms: number) {
    setRange(ms);
    setCustom(false);
    setQuery({ start: Date.now() - ms, end: Date.now() });
  }
  function applyCustom() {
    const from = Date.parse(start),
      to = Date.parse(end);
    if (!Number.isFinite(from) || !Number.isFinite(to) || from >= to) {
      setError("Choose a start time before the end time.");
      return;
    }
    if (to - from > 31 * 86400000) {
      setError("Choose a range of 31 days or less.");
      return;
    }
    setMode("history");
    setQuery({ start: from, end: to });
    setError("");
  }
  function exportCsv() {
    const rows = [
      "timestamp_utc,timestamp_local,channel,value_mv",
      ...data.map(
        (point) =>
          `${new Date(point.timestamp_ms).toISOString()},"${new Date(point.timestamp_ms).toLocaleString().replaceAll('"', '""')}",${key},${point[key] ?? ""}`,
      ),
    ];
    const url = URL.createObjectURL(
      new Blob([rows.join("\r\n")], { type: "text/csv;charset=utf-8;" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `${deviceId}_${key}_${mode}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }
  const valid = !!received && !!(received.valid_mask & (1 << (channel - 1)));
  const mapping = device?.mapping?.find(
    (item) => item.channel === key,
  )?.physical;
  return (
    <>
      <Link to="/" className="back-link">
        <ArrowLeft size={14} />
        Telemetry overview
      </Link>
      <div className="page-heading">
        <div>
          <div className="heading-row">
            <h1>{channelName(channel)} analytics</h1>
            <StatusBadge
              state={isFresh(received, now) && valid ? "good" : "warning"}
            >
              {isFresh(received, now) && valid
                ? "Live signal"
                : "Signal unavailable"}
            </StatusBadge>
          </div>
          <p>
            {deviceId} <span className="dot-divider">·</span>{" "}
            {mapping || channelMapping(channel)}
          </p>
        </div>
        <label className="select-field">
          Channel
          <select
            value={channel}
            onChange={(event) =>
              navigate(`/analytics/analog-${event.target.value}`)
            }
            aria-label="Analytics channel"
          >
            {[...Array(CHANNEL_COUNT)].map((_, i) => (
              <option value={i + 1} key={i}>
                {channelName(i + 1)}
              </option>
            ))}
          </select>
        </label>
      </div>
      {received?.source === "simulator" && (
        <div className="notice simulator">
          <ChartNoAxesCombined size={17} />
          <span>
            Simulator signals · Values are generated for integration testing.
          </span>
        </div>
      )}
      {connection !== "connected" && (
        <div className="notice warning">
          <TriangleAlert size={17} />
          <span>
            Live connection{" "}
            {connection === "connecting" ? "is connecting" : "was interrupted"}.
            Historical measurements remain available when the backend is
            reachable.
          </span>
        </div>
      )}
      <div className="analytics-stat-grid">
        <Statistic
          label="LATEST READING"
          value={valid ? received?.channels[key] : null}
          unit="mV"
          detail={age(received?.received_at, now)}
        />
        <Statistic
          label="MINIMUM"
          value={stats.min}
          unit="mV"
          detail={
            mode === "history"
              ? "Across selected history range"
              : "Across the visible live window"
          }
        />
        <Statistic
          label="MAXIMUM"
          value={stats.max}
          unit="mV"
          detail={`${numeric(stats.count)} valid measurements`}
        />
        <Statistic
          label="AVERAGE"
          value={stats.avg}
          unit="mV"
          detail={
            mode === "history"
              ? "Computed by the backend"
              : "Across the visible live window"
          }
          digits={1}
        />
      </div>
      <section className="panel analytics-panel">
        <div className="panel-heading">
          <div>
            <h2>
              <ChartNoAxesCombined size={18} />
              Signal history
            </h2>
            <p>
              {mode === "live"
                ? "Live samples from the current browser session"
                : "Persisted measurements with server-side downsampling"}
            </p>
          </div>
          <button
            className="button secondary small"
            onClick={exportCsv}
            disabled={!data.length}
          >
            <ArrowDownToLine size={14} />
            Export plotted CSV
          </button>
        </div>
        <div className="analytics-toolbar">
          <div className="segmented">
            <button
              className={mode === "live" ? "active" : ""}
              onClick={() => setMode("live")}
            >
              Live
            </button>
            <button
              className={mode === "history" ? "active" : ""}
              onClick={() => {
                setMode("history");
                setQuery({ start: Date.now() - range, end: Date.now() });
              }}
            >
              Historical
            </button>
          </div>
          <div className="range-presets">
            {presets.map((preset) => (
              <button
                className={!custom && preset.ms === range ? "active" : ""}
                key={preset.ms}
                onClick={() => choosePreset(preset.ms)}
              >
                {preset.label}
              </button>
            ))}
            <button
              className={custom ? "active" : ""}
              onClick={() => {
                setCustom(true);
                setMode("history");
              }}
            >
              Custom
            </button>
          </div>
          <button
            className="icon-button"
            aria-label="Refresh history"
            disabled={loading}
            onClick={() =>
              setQuery(
                custom
                  ? { start: Date.parse(start), end: Date.parse(end) }
                  : { start: Date.now() - range, end: Date.now() },
              )
            }
          >
            <RefreshCw size={16} className={loading ? "spinning" : ""} />
          </button>
        </div>
        {custom && (
          <div className="custom-range">
            <label>
              From
              <input
                aria-label="Range start"
                type="datetime-local"
                value={start}
                onChange={(event) => setStart(event.target.value)}
              />
            </label>
            <label>
              To
              <input
                aria-label="Range end"
                type="datetime-local"
                value={end}
                onChange={(event) => setEnd(event.target.value)}
              />
            </label>
            <button className="button primary small" onClick={applyCustom}>
              Apply range
            </button>
            <span>Local timezone</span>
          </div>
        )}
        {error && (
          <div className="notice warning" role="alert">
            <TriangleAlert size={16} />
            <span>{error}</span>
          </div>
        )}
        <div className="analytics-chart-label">
          <span>VOLTAGE · mV</span>
          <span>
            <Clock3 size={12} />
            {mode === "history"
              ? `${dateTime(query.start)} – ${dateTime(query.end)}`
              : `Rolling ${presets.find((item) => item.ms === range)?.label || "window"} · up to 600 live samples`}
          </span>
        </div>
        {loading ? (
          <div className="chart-loading" role="status">
            <RefreshCw size={23} className="spinning" />
            <p>Loading persisted measurements…</p>
          </div>
        ) : (
          <TelemetryChart data={data} channels={[channel]} height={370} brush />
        )}
        <div className="chart-foot">
          <span>
            <Maximize2 size={13} />
            Drag range handles to zoom. Slide the selection to pan.
          </span>
          <span>
            {history?.downsampled && mode === "history"
              ? "Bucket averages shown · statistics use source readings"
              : "Original timestamps · UTC included in CSV"}
          </span>
        </div>
      </section>
      <div className="analytics-notes">
        <div>
          <span className="eyebrow">DATA FRESHNESS</span>
          <p>
            Last received: <strong>{dateTime(received?.received_at)}</strong>
          </p>
          <p>
            Device acquisition time:{" "}
            <strong>
              {received?.time_valid
                ? dateTime(received.timestamp_ms)
                : "Device clock unsynchronized"}
            </strong>
          </p>
        </div>
        <div>
          <span className="eyebrow">READING THIS CHART</span>
          <p>
            Invalid channels appear as gaps. Historical statistics include valid
            source readings in the selected range. CSV exports the points
            currently plotted.
          </p>
        </div>
      </div>
    </>
  );
}
function Statistic({
  label,
  value,
  unit,
  detail,
  digits = 0,
}: {
  label: string;
  value?: number | null;
  unit: string;
  detail: string;
  digits?: number;
}) {
  return (
    <div className="metric-card">
      <span className="metric-top">{label}</span>
      <div className="metric-value">
        {numeric(value, digits)}
        <small>{unit}</small>
      </div>
      <div className="metric-caption">{detail}</div>
    </div>
  );
}
