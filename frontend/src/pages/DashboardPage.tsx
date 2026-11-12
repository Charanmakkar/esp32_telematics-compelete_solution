import { useMemo, useState } from "react";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  Check,
  Cpu,
  Database,
  Layers3,
  Radio,
  RefreshCw,
  Server,
  ShieldCheck,
  Timer,
  TriangleAlert,
  Wifi,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useTelemetry } from "../hooks/useTelemetry";
import { StatusBadge } from "../components/StatusBadge";
import { ChannelCard } from "../components/ChannelCard";
import {
  TelemetryChart,
  channelColors,
  type PlotPoint,
} from "../charts/TelemetryChart";
import {
  age,
  dateTime,
  isFresh,
  numeric,
  sampleTime,
} from "../services/format";

export function DashboardPage() {
  const {
    deviceId,
    device,
    received,
    persisted,
    samples,
    health,
    connection,
    error,
    loading,
    now,
    refresh,
  } = useTelemetry();
  const [visible, setVisible] = useState([1, 2, 3]);
  const metrics = health?.metrics;
  const fresh = isFresh(received, now);
  const validCount = received
    ? [...Array(6)].filter((_, n) => received.valid_mask & (1 << n)).length
    : 0;
  const chartData = useMemo<PlotPoint[]>(
    () =>
      (samples.length ? samples : received ? [received] : []).map((sample) => ({
        timestamp_ms: sampleTime(sample) || Date.now(),
        ...Object.fromEntries(
          [...Array(6)].map((_, n) => [
            `analog_${n + 1}`,
            sample.valid_mask & (1 << n)
              ? sample.channels[`analog_${n + 1}`]
              : null,
          ]),
        ),
      })),
    [samples, received],
  );
  function toggle(channel: number) {
    setVisible((current) =>
      current.includes(channel)
        ? current.length > 1
          ? current.filter((n) => n !== channel)
          : current
        : [...current, channel],
    );
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="heading-row">
            <h1>Telemetry overview</h1>
            <StatusBadge
              state={fresh ? "good" : received ? "warning" : "neutral"}
            >
              {fresh
                ? "Device online"
                : received
                  ? "Data stale"
                  : "Awaiting device"}
            </StatusBadge>
          </div>
          <p>
            Every signal. Every moment. A clearer view of your connected world.
          </p>
        </div>
        <button
          className="button secondary"
          onClick={() => void refresh()}
          disabled={loading}
        >
          <RefreshCw size={15} className={loading ? "spinning" : ""} />
          Refresh status
        </button>
      </div>
      {error && (
        <div className="notice warning" role="alert">
          <TriangleAlert size={17} />
          <span>{error}</span>
          <button onClick={() => void refresh()}>Retry</button>
        </div>
      )}
      {received?.source === "simulator" && (
        <div className="notice simulator">
          <Cpu size={17} />
          <span>
            <strong>Simulator session</strong> · These values are generated test
            signals. No hardware measurements are being displayed.
          </span>
        </div>
      )}
      {connection === "disconnected" && (
        <div className="notice warning">
          <Wifi size={17} />
          <span>
            Live stream interrupted. Reconnecting automatically; displayed
            measurements retain their original timestamps.
          </span>
        </div>
      )}
      <section className="metric-grid" aria-label="Platform metrics">
        <div className="metric-card">
          <div className="metric-top">
            <span>TELEMETRY RATE</span>
            <span className="metric-icon cyan">
              <Activity size={17} />
            </span>
          </div>
          <div className="metric-value">
            {numeric(metrics?.frequency_hz, 1)}
            <small>Hz</small>
          </div>
          <div className="metric-caption">
            <span className={`status-dot ${fresh ? "online" : ""}`} />
            Measured ingest rate{" "}
            <span className="metric-target">Target 10 Hz</span>
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-top">
            <span>RECORDS RECEIVED</span>
            <span className="metric-icon blue">
              <Layers3 size={17} />
            </span>
          </div>
          <div className="metric-value">{numeric(metrics?.received)}</div>
          <div className="metric-caption">
            <ArrowDownToLine size={12} />
            {numeric(metrics?.persisted)} successfully persisted
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-top">
            <span>ACTIVE CHANNELS</span>
            <span className="metric-icon green">
              <Radio size={17} />
            </span>
          </div>
          <div className="metric-value">
            {received ? validCount : "—"}
            <small>/ 6</small>
          </div>
          <div className="metric-caption">
            {received
              ? `${6 - validCount} channel${6 - validCount === 1 ? "" : "s"} unavailable`
              : "Waiting for first sample"}
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-top">
            <span>MESSAGE QUALITY</span>
            <span className="metric-icon amber">
              <ShieldCheck size={17} />
            </span>
          </div>
          <div className="metric-value">
            {numeric((metrics?.invalid ?? 0) + (metrics?.dropped ?? 0))}
            <small>issues</small>
          </div>
          <div className="metric-caption">
            {numeric(metrics?.invalid ?? 0)} invalid{" "}
            <span className="dot-divider">·</span>{" "}
            {numeric(metrics?.dropped ?? 0)} dropped
          </div>
        </div>
      </section>
      <section className="overview-middle">
        <div className="panel live-panel">
          <div className="panel-heading">
            <div>
              <h2>
                <Activity size={17} />
                Live signal monitor
              </h2>
              <p>Incoming measurements · millivolts (mV)</p>
            </div>
            <span className="live-indicator">
              <span className={`status-dot ${fresh ? "online" : ""}`} />
              {fresh ? "LIVE" : "NO LIVE DATA"}
            </span>
          </div>
          <div className="chart-legend">
            {[1, 2, 3, 4, 5].map((channel) => (
              <button
                key={channel}
                className={visible.includes(channel) ? "selected" : ""}
                onClick={() => toggle(channel)}
                aria-pressed={visible.includes(channel)}
              >
                <span style={{ background: channelColors[channel - 1] }} />
                Analog {String(channel).padStart(2, "0")}
              </button>
            ))}
            <Link to="/analytics/analog-1">
              All channels
              <ArrowRight size={12} />
            </Link>
          </div>
          <TelemetryChart data={chartData} channels={visible} height={245} />
          <div className="chart-foot">
            <span>
              <Timer size={12} />
              Latest 600 live samples · original acquisition timestamps
            </span>
            <span>
              {received
                ? `Sequence #${received.sequence.toLocaleString()}`
                : "No sequence received"}
            </span>
          </div>
        </div>
        <div className="panel pipeline-panel">
          <div className="panel-heading">
            <div>
              <h2>System health</h2>
              <p>From edge to insight</p>
            </div>
            <span className="mini-label">4 SERVICES</span>
          </div>
          <div className="pipeline-list">
            <HealthRow
              icon={<Cpu size={17} />}
              title="ESP32 device"
              subtitle={deviceId}
              good={fresh}
              status={fresh ? "Online" : received ? "Stale" : "Waiting"}
            />
            <HealthRow
              icon={<Wifi size={17} />}
              title="MQTT broker"
              subtitle="Authenticated message transport"
              good={!!health?.mqtt_connected}
              status={health?.mqtt_connected ? "Connected" : "Disconnected"}
            />
            <HealthRow
              icon={<Server size={17} />}
              title="Python backend"
              subtitle="Validation & live streaming"
              good={!!health}
              status={health ? "Operational" : "Unreachable"}
            />
            <HealthRow
              icon={<Database size={17} />}
              title="Database"
              subtitle="Persistent measurement storage"
              good={!!health?.database_connected}
              status={health?.database_connected ? "Connected" : "Unavailable"}
            />
          </div>
          <div className="pipeline-summary">
            <span>
              <span className="status-dot" /> Health refresh
            </span>
            <strong>{health ? "Every 10 seconds" : "Pending"}</strong>
          </div>
        </div>
      </section>
      <section className="channels-section">
        <div className="section-heading">
          <div>
            <h2>
              Analog channels <span className="count-badge">6</span>
            </h2>
            <p>
              Live inputs with a separate confirmation of database persistence.
            </p>
          </div>
          <span className="section-hint">
            <span className="status-dot online" />
            {received
              ? `Updated ${age(received.received_at, now).toLowerCase()}`
              : "Ready to receive"}
          </span>
        </div>
        <div className="channel-grid">
          {[...Array(6)].map((_, index) => (
            <ChannelCard
              key={index + 1}
              channel={index + 1}
              received={received}
              persisted={persisted}
              data={chartData}
              mapping={
                device?.mapping?.find(
                  (mapping) => mapping.channel === `analog_${index + 1}`,
                )?.physical
              }
              now={now}
            />
          ))}
        </div>
      </section>
      <section
        className="ingest-strip"
        aria-label="Data arrival and persistence"
      >
        <div>
          <span className="strip-icon">
            <Radio size={17} />
          </span>
          <span>
            <small>LAST RECEIVED</small>
            <strong>{dateTime(received?.received_at)}</strong>
          </span>
        </div>
        <span className="ingest-arrow">
          <ArrowRight size={17} />
        </span>
        <div>
          <span className="strip-icon">
            <Database size={17} />
          </span>
          <span>
            <small>LAST PERSISTED</small>
            <strong>
              {dateTime(persisted?.persisted_at || persisted?.received_at)}
            </strong>
          </span>
        </div>
        <div className="integrity-note">
          <Check size={16} />
          <span>
            Received data is shown live.
            <br />
            Persistence is confirmed separately.
          </span>
        </div>
      </section>
    </>
  );
}
function HealthRow({
  icon,
  title,
  subtitle,
  good,
  status,
}: {
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  good: boolean;
  status: string;
}) {
  return (
    <div className="health-row">
      <span className={`health-icon ${good ? "healthy" : ""}`}>{icon}</span>
      <div>
        <strong>{title}</strong>
        <small>{subtitle}</small>
      </div>
      <span className={`health-state ${good ? "healthy" : ""}`}>
        <span className="status-dot" />
        {status}
      </span>
    </div>
  );
}
