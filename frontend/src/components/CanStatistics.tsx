import { useEffect, useState } from "react";
import { request } from "../services/api";

type Stats = { available: boolean; reason?: string; age_seconds: number; unique_ids: number;
  window_seconds: number; received_fps: number; received_bytes_per_second: number;
  hardware_fps: number | null; load_min_percent: number | null; load_max_percent: number | null;
  totals: Record<string, number>; device: Record<string, number | string | null>; dlc_distribution: number[];
  load_note: string; timing_note: string;
  ids: { can_id: number; extended: boolean; rtr: boolean; frames: number; dlc: number; changes: number;
    age_seconds: number; mean_interval_ms: number | null; min_interval_ms: number | null;
    max_interval_ms: number | null; jitter_ms: number | null; frequency_hz: number | null }[] };
const value = (v: unknown) => v == null ? "Not available" : String(v);

export function CanStatistics({ deviceId }: { deviceId: string }) {
  const [data, setData] = useState<Stats | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    setData(null);
    async function poll() {
      try {
        const next = await request<Stats>(`/api/v1/can/statistics?device_id=${encodeURIComponent(deviceId)}`, { signal: controller.signal });
        if (active) { setData(next); setError(""); }
      } catch (e) { if (active) setError((e as Error).message); }
      if (active) timer = setTimeout(poll, 2000);
    }
    void poll();
    return () => { active = false; controller.abort(); clearTimeout(timer); };
  }, [deviceId]);
  return <details className="can-statistics">
    <summary>CAN statistics & protocol details</summary>
    {error && <p role="alert">{error}</p>}
    {!data?.available ? <p>{data?.reason || "Waiting for CAN statistics…"}</p> : <>
      <p className={data.age_seconds > 5 ? "can-warning" : "can-good"}>
        {data.age_seconds > 5 ? `Statistics stale (${data.age_seconds}s)` : "Statistics live"} · 10-second traffic window · {data.unique_ids} observed IDs
      </p>
      <div className="can-stat-grid">
        <article><small>Captured on ESP32</small><strong>{value(data.hardware_fps)} {data.hardware_fps != null && "frames/s"}</strong></article>
        <article><small>Delivered to server</small><strong>{data.received_fps} frames/s</strong></article>
        <article><small>Estimated bus utilization</small><strong>{data.load_min_percent == null ? "Requires updated firmware" : `${data.load_min_percent}–${data.load_max_percent}%`}</strong></article>
        <article><small>Payload delivered</small><strong>{data.received_bytes_per_second} bytes/s</strong></article>
      </div>
      <p>{data.load_note}</p>
      <div className="can-stat-grid">
        {[["Standard frames", "standard_frames", "standard"], ["Extended frames", "extended_frames", "extended"], ["Remote requests", "rtr_frames", "rtr"]].map(([label, hw, fallback]) =>
          <article key={label}><small>{label}</small><strong>{value(data.device[hw] ?? data.totals[fallback] ?? 0)}</strong><small>{data.device[hw] == null ? "delivered since monitoring started" : "captured since ESP32 boot"}</small></article>)}
        <article><small>Controller / mode</small><strong>{["Stopped", "Running", "Bus off", "Recovering"][Number(data.device.controller_state ?? -1)] || "Not available"}</strong><small>{String(data.device.mode || "Listen only (legacy firmware)").replaceAll("_", " ")}</small></article>
      </div>
      <h3>Controller health</h3>
      <dl className="can-health-grid">{[
        ["RX error counter", "rx_error_counter"], ["TX error counter", "tx_error_counter"],
        ["Bus errors", "bus_errors"], ["Arbitration losses", "arb_lost"], ["TX failures", "tx_failed"],
        ["Diagnostic TX frames", "tx_frames"], ["RX missed", "rx_missed"], ["RX overruns", "rx_overruns"],
        ["Capture queue drops", "queue_drops"], ["MQTT publish drops", "publish_drops"],
        ["Serial output drops", "serial_drops"], ["Mode-switch gaps (frames)", "mode_switch_drops"],
      ].map(([label, key]) => <div key={key}><dt>{label}</dt><dd>{value(data.device[key])}</dd></div>)}</dl>
      <h3>DLC distribution</h3><div className="can-dlc-bars">{data.dlc_distribution.map((count, dlc) =>
        <div key={dlc}><span>{dlc} bytes</span><meter min="0" max={Math.max(1, ...data.dlc_distribution)} value={count} /><strong>{count}</strong></div>)}</div>
      <h3>Per-ID timing and activity</h3><p>{data.timing_note} Most active 100 IDs; stale IDs keep their last measured timing.</p>
      <div className="can-table-wrap"><table className="can-table"><thead><tr><th>ID / format</th><th>Frames</th><th>Rate (Hz)</th><th>Interval avg / min / max (ms)</th><th>Jitter (ms)</th><th>Changes</th><th>Age (s)</th></tr></thead>
        <tbody>{data.ids.map(i => <tr key={`${i.can_id}-${i.extended}-${i.rtr}`}><td>0x{i.can_id.toString(16).toUpperCase()} · {i.extended ? "EXT" : "STD"} {i.rtr && "RTR"}</td><td>{i.frames}</td><td>{value(i.frequency_hz)}</td><td>{value(i.mean_interval_ms)} / {value(i.min_interval_ms)} / {value(i.max_interval_ms)}</td><td>{value(i.jitter_ms)}</td><td>{i.changes}</td><td>{i.age_seconds}</td></tr>)}</tbody></table></div>
    </>}
    <h3>Bus and protocol reference</h3>
    <dl className="can-health-grid">
      <div><dt>Physical bus</dt><dd>Classic CAN · 500 kbit/s · 2 μs/bit · TJA1042</dd></div>
      <div><dt>ESP32 pins</dt><dd>GPIO25 TX · GPIO26 RX · common ground</dd></div>
      <div><dt>Identifiers</dt><dd>11-bit standard (0–0x7FF); 29-bit extended (0–0x1FFFFFFF)</dd></div>
      <div><dt>Frames</dt><dd>DATA: 0–8 payload bytes. RTR: a remote request with no payload. CAN FD is unsupported.</dd></div>
      <div><dt>Arbitration</dt><dd>Dominant bits win arbitration; lower IDs normally have higher priority.</dd></div>
      <div><dt>Frame layout</dt><dd>SOF → arbitration → control/DLC → data → CRC-15 → ACK → EOF → intermission</dd></div>
      <div><dt>Fault confinement</dt><dd>Error passive at TEC or REC ≥128. Bus off when TEC exceeds 255. Driver state is authoritative.</dd></div>
      <div><dt>DBC / diagnostics</dt><dd>DBC defines payload signals. UDS requests use ISO-TP segmentation and flow control on the BMS page.</dd></div>
    </dl>
    <p>Voltage, termination resistance, ACK-slot measurements and individual CRC/stuff/bit error classifications require additional test equipment and are not measured here. Listen-only mode does not acknowledge frames; diagnostic mode temporarily enables normal CAN participation.</p>
  </details>;
}
