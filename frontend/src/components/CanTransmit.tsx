import { useEffect, useRef, useState } from "react";
import { request } from "../services/api";

type TxSnapshot = {
  supported: boolean; fresh: boolean; clock_ready: boolean; boot_id: string | null; mode: string | null;
  profiles: { can_id: number; data: string; dlc: number; period_ms: number }[];
  state: { enabled: boolean; reason: string; sent_014: number; sent_548: number;
    failures: number; skipped: number } | null;
};
const reasons: Record<string, string> = {
  connection_lost: "Stopped after the ESP32 lost its MQTT connection.",
  transmit_failed: "Stopped after repeated CAN send failures. Check the bus connection and ACK.",
  controller_busy_or_unavailable: "Unable to start: the CAN controller is unavailable or diagnostics are active.",
};

export function CanTransmit({ deviceId, canControl }: { deviceId: string; canControl: boolean }) {
  const [snapshot, setSnapshot] = useState<TxSnapshot | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const generation = useRef(0);
  useEffect(() => {
    const controller = new AbortController();
    generation.current++; pending.current = false;
    setSnapshot(null); setError(""); setBusy(false);
    let fetching = false;
    async function refresh() {
      if (fetching || pending.current) return;
      fetching = true;
      const current = generation.current;
      try {
        const next = await request<TxSnapshot>(`/api/v1/can/tx?device_id=${encodeURIComponent(deviceId)}`,
          { signal: AbortSignal.any([controller.signal, AbortSignal.timeout(8000)]) });
        if (!controller.signal.aborted && current === generation.current) setSnapshot(next);
      } catch {
        if (!controller.signal.aborted && current === generation.current)
          setSnapshot(previous => previous ? { ...previous, fresh: false } : null);
      } finally { fetching = false; }
    }
    void refresh(); const timer = setInterval(refresh, 1000);
    return () => { controller.abort(); clearInterval(timer); generation.current++; };
  }, [deviceId]);
  async function toggle(enabled: boolean) {
    if (pending.current) return;
    pending.current = true; setBusy(true); setError("");
    const current = ++generation.current;
    try {
      const next = await request<TxSnapshot>("/api/v1/can/tx", {
        method: "POST", body: JSON.stringify({ device_id: deviceId, enabled }),
        signal: AbortSignal.timeout(8000),
      });
      if (current === generation.current) {
        setSnapshot(next);
        if (next.state?.enabled !== enabled) setError(reasons[next.state?.reason || ""] || "The ESP32 did not apply the requested state.");
      }
    } catch (e) {
      if (current === generation.current) {
        setError((e as Error).message);
        setSnapshot(previous => previous ? { ...previous, fresh: false } : null);
      }
    } finally {
      if (current === generation.current) { pending.current = false; setBusy(false); }
    }
  }
  const fresh = !!snapshot?.fresh;
  const on = !!snapshot?.state?.enabled;
  const stop = on || !fresh;
  return <section className="can-transmit" aria-label="Periodic CAN transmission">
    <div className="can-transmit-heading"><div><h2>Periodic CAN transmission</h2>
      <p>Send both fixed messages from this ESP32 at 500 kbit/s.</p></div>
      <strong className={fresh ? "can-good" : "can-warning"} aria-live="polite">
        {busy ? "Waiting for ESP32 confirmation…" : fresh ? on ? "Transmission ON" : "Transmission OFF" : "Transmission state unknown"}
      </strong></div>
    <div className="can-table-wrap"><table className="can-table" aria-label="Periodic CAN messages">
      <thead><tr><th>CAN ID</th><th>Data bytes</th><th>DLC</th><th>Period</th><th>Successful sends</th></tr></thead>
      <tbody>{(snapshot?.profiles || [
        { can_id: 0x014, data: "006000", dlc: 3, period_ms: 100 },
        { can_id: 0x548, data: "0000000000000008", dlc: 8, period_ms: 10 },
      ]).map(frame => <tr key={frame.can_id}>
        <td><strong>0x{frame.can_id.toString(16).toUpperCase().padStart(3, "0")}</strong></td>
        <td><code>{frame.data.match(/../g)?.join(" ")}</code></td><td>{frame.dlc}</td><td>{frame.period_ms} ms</td>
        <td>{snapshot?.state ? frame.can_id === 0x014 ? snapshot.state.sent_014 : snapshot.state.sent_548 : "—"}</td>
      </tr>)}</tbody></table></div>
    <div className="can-transmit-controls">
      {canControl && <button disabled={busy || !snapshot?.supported || (!stop && (!snapshot.clock_ready || (snapshot.mode !== "listen_only" && snapshot.mode !== "periodic_tx")))}
        onClick={() => void toggle(!stop)}>{stop ? "Turn transmission OFF" : "Turn transmission ON"}</button>}
      <span>Standard CAN · fixed payloads · both messages switch together.</span>
    </div>
    <p>Starts OFF after a restart. Stops on a lost MQTT connection or repeated send failures. Diagnostics must be idle to turn ON.</p>
    {snapshot?.state && <small>Counters since ESP32 restart: {snapshot.state.failures} failed sends · {snapshot.state.skipped} missed schedule slots.
      {!fresh && ` Last confirmed state: ${on ? "ON" : "OFF"}.`}</small>}
    {snapshot && !snapshot.supported && <p className="can-warning">Waiting for ESP32 firmware with transmission control.</p>}
    {snapshot?.supported && fresh && !on && !snapshot.clock_ready && <p className="can-warning">Waiting for the ESP32 clock to synchronize before turning ON.</p>}
    {snapshot?.state && reasons[snapshot.state.reason] && <p className="can-warning">{reasons[snapshot.state.reason]}</p>}
    {error && <p role="alert" className="error-text">{error}</p>}
  </section>;
}
