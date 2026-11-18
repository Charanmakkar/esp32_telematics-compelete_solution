import { useEffect, useState } from "react";
import { useTelemetry } from "../hooks/useTelemetry";
import { useAuth } from "../hooks/useAuth";
import { request } from "../services/api";
import { CanStatistics } from "../components/CanStatistics";

type Signal = { name: string; value: number | null; unit?: string; label?: string };
type Frame = { can_id: number; extended: boolean; rtr: boolean; dlc: number; data: string;
  boot_id?: string;
  sequence: number; uptime_ms: number; timestamp_ms: number; received_at: string;
  frame_count: number; decode_status: string; message_name?: string; signals: Signal[];
  dbc_file?: string; dbc_files?: string[] };
type DbcLibrary = { folder: string; messages: number; errors: string[];
  files: { filename: string; status: string; messages: number; error?: string }[];
  conflicts: { can_id: number; extended: boolean; files: string[] }[] };
type Snapshot = { frames: Frame[]; has_more: boolean; dbc: { filename?: string } | null;
  current_boot_id?: string | null; server_time?: string;
  dbc_library?: DbcLibrary;
  status: ({ received_at: string; boot_id: string } & Record<string, number | string>) | null;
  metrics: Record<string, number> };

export function CanPage() {
  const { deviceId } = useTelemetry();
  const { user } = useAuth();
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [view, setView] = useState("current");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [resultQuery, setResultQuery] = useState("");
  const [lastRefresh, setLastRefresh] = useState<number | null>(null);
  const [history, setHistory] = useState<Frame[] | null>(null);
  const [historyId, setHistoryId] = useState("");
  const [tick, setTick] = useState(Date.now());
  useEffect(() => { setOffset(0); setSnapshot(null); setHistory(null); setNotice(""); setLastRefresh(null); }, [deviceId]);
  useEffect(() => {
    const clock = setInterval(() => setTick(Date.now()), 1000);
    return () => clearInterval(clock);
  }, []);
  useEffect(() => {
    const next = search.trim();
    if (next === query) return;
    const timer = setTimeout(() => { setQuery(next); setOffset(0); setHistory(null); }, 250);
    return () => clearTimeout(timer);
  }, [search, query]);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    let controller: AbortController | undefined;
    async function poll() {
      controller = new AbortController();
      const timeout = setTimeout(() => controller?.abort(), 8000);
      try {
        const result = await request<Snapshot>(`/api/v1/can/latest?device_id=${encodeURIComponent(deviceId)}&offset=${offset}&current_boot_only=${view === "current"}&search=${encodeURIComponent(query)}`, { signal: controller.signal, cache: "no-store" });
        if (active) { setSnapshot(result); setResultQuery(query); setLastRefresh(Date.now()); setError(""); }
      } catch (e) {
        if (active) setError((e as Error).name === "AbortError" ? "CAN update timed out. Retrying…" : (e as Error).message);
      } finally { clearTimeout(timeout); }
      if (active) { setTick(Date.now()); timer = setTimeout(poll, 1000); }
    }
    void poll();
    return () => { active = false; controller?.abort(); clearTimeout(timer); };
  }, [deviceId, offset, refresh, view, query]);

  async function upload(files: File[]) {
    if (!files.length) return;
    setBusy(true); setNotice("");
    const results: string[] = [];
    for (const file of files) {
      try {
        if (!file.name.toLowerCase().endsWith(".dbc") || file.size > 2 * 1024 * 1024)
          throw new Error("Choose a .dbc file up to 2 MiB.");
        const result = await request<{ messages: number }>("/api/v1/can/dbc/files", {
          method: "POST", body: JSON.stringify({ filename: file.name, content: await file.text() }),
        });
        results.push(`${file.name}: saved ${result.messages} message definitions.`);
      } catch (e) { results.push(`${file.name}: ${(e as Error).message}`); }
    }
    setNotice(results.join(" ")); setRefresh(n => n + 1); setBusy(false);
  }
  async function showHistory(frame: Frame) {
    try {
      const result = await request<{ frames: Frame[] }>(`/api/v1/can/history?device_id=${encodeURIComponent(deviceId)}&can_id=${frame.can_id}&extended=${frame.extended}&limit=50`);
      setHistory(result.frames); setHistoryId(hexId(frame));
    } catch (e) { setError((e as Error).message); }
  }
  const serverNow = snapshot?.server_time && lastRefresh != null ? Date.parse(snapshot.server_time) + tick - lastRefresh : tick;
  const age = (at: string) => Math.max(0, (serverNow - Date.parse(at)) / 1000);
  const connected = snapshot?.status && age(snapshot.status.received_at) < 5 && !error;
  const filtering = search.trim() !== resultQuery;
  return <section className="can-page">
    <div className="page-heading"><div><h1>CAN data</h1>
      <p>500 kbit/s · {snapshot?.status?.mode === "diagnostic" ? "Diagnostics active" : "Listen only"} · GPIO25 TX / GPIO26 RX · Classic CAN</p></div></div>
    <p role="status" className={connected ? "can-good" : "can-warning"}>
      {connected ? "CAN logger online" : "Waiting for CAN logger / stale connection"} — latest values refresh every second.
    </p>
    {error && <p role="alert" className="error-text">{error} Last displayed values may be stale.</p>}
    <div className="can-live-toolbar">
      <label>Show IDs <select aria-label="CAN frame view" value={view} onChange={e => {
        setView(e.target.value); setOffset(0); setSnapshot(null); setLastRefresh(null); setHistory(null);
      }}><option value="current">Current ESP32 run</option><option value="all">All saved IDs</option></select></label>
      <span>Last refresh: <strong>{lastRefresh == null ? "Waiting…" : new Date(lastRefresh).toLocaleTimeString()}</strong></span>
      <button onClick={() => setRefresh(n => n + 1)}>Refresh now</button>
    </div>
    <p className="can-view-note">{view === "current" ? "Showing IDs received since this ESP32 started. Previous runs remain in All saved IDs and history." : "Showing all saved IDs. Previous-run values keep their original timestamp."}</p>
    <div className="can-search">
      <label htmlFor="can-live-search">Search CAN messages</label>
      <div className="can-search-controls">
        <input id="can-live-search" type="search" maxLength={128} value={search}
          placeholder="e.g. 0x06E, BMS_VCU or 38 DE" aria-describedby="can-search-help"
          onChange={e => setSearch(e.target.value)} />
        <button disabled={!search && !query} onClick={() => {
          setSearch(""); setQuery(""); setOffset(0); setHistory(null);
        }}>Clear search</button>
      </div>
      <small id="can-search-help">Search all IDs in this view by hex CAN ID, message or signal name, DBC filename, or raw bytes. Live updates continue.</small>
    </div>
    <div className="can-table-wrap can-latest-table"><table className="can-table" aria-label="Latest CAN values"><thead><tr>
      <th>CAN ID</th><th>Type / DLC</th><th>Last raw bytes</th><th>Decoded signals</th><th>Seen / count</th><th>History</th>
    </tr></thead><tbody>
      {filtering ? <tr><td colSpan={6}>Searching CAN messages…</td></tr> : !snapshot?.frames.length && <tr><td colSpan={6}>
        {query ? `No CAN messages match “${query}”. Clear search to show all IDs in this view.` : `No CAN frames recorded ${view === "current" ? "for this ESP32 run" : "yet"}. Raw capture does not require a DBC.`}
      </td></tr>}
      {!filtering && snapshot?.frames.map(f => <tr key={`${f.can_id}-${f.extended}-${f.rtr}`}>
        <td><strong>{hexId(f)}</strong><div>{f.message_name || "Unmapped message"}</div>{f.dbc_file && <small>{f.dbc_file}</small>}</td>
        <td>{f.extended ? "Extended" : "Standard"}{f.rtr ? " RTR" : ""}<div>DLC {f.dlc}</div></td>
        <td><code key={f.data} className="can-changing-value">{f.rtr ? "Remote request" : f.data.match(/../g)?.join(" ") || "(empty)"}</code></td>
        <td>{f.signals.length ? <>
          {f.signals.slice(0, 2).map(s => <div key={s.name}><strong>{s.name}</strong>: {s.value ?? "N/A"} {s.unit} {s.label && `(${s.label})`}</div>)}
          {f.signals.length > 2 && <details className="can-more-signals"><summary>{f.signals.length - 2} more signals</summary>
            {f.signals.slice(2).map(s => <div key={s.name}><strong>{s.name}</strong>: {s.value ?? "N/A"} {s.unit} {s.label && `(${s.label})`}</div>)}
          </details>}
        </> : f.decode_status === "dbc_conflict" ? `DBC conflict: ${f.dbc_files?.join(", ")}` : f.decode_status.replaceAll("_", " ")}</td>
        <td><span className={age(f.received_at) > 5 ? "can-warning" : ""}>{age(f.received_at).toFixed(1)}s ago</span><div>{f.frame_count} frames</div>{snapshot.current_boot_id && f.boot_id !== snapshot.current_boot_id && <small>Previous run</small>}</td>
        <td><button onClick={() => void showHistory(f)}>View</button></td>
      </tr>)}
    </tbody></table></div>
    <div className="can-pagination"><button disabled={filtering || offset === 0} onClick={() => setOffset(Math.max(0, offset - 100))}>Previous IDs</button>
      <span>{filtering ? "Searching…" : snapshot?.frames.length ? `${query ? "Matching IDs" : "IDs"} ${offset + 1}–${offset + snapshot.frames.length}` : "No IDs"}</span>
      <button disabled={filtering || !snapshot?.has_more} onClick={() => setOffset(offset + 100)}>Next IDs</button></div>
    {history && <section><h2>Recent history: {historyId}</h2><button onClick={() => setHistory(null)}>Close history</button>
      <p>Last 50 stored frames for this ID and format, newest first.</p>
      <div className="can-table-wrap"><table className="can-table"><thead><tr><th>Received</th><th>Sequence</th><th>DLC</th><th>Data</th></tr></thead><tbody>
        {history.map((f, i) => <tr key={i}><td>{new Date(f.received_at).toLocaleString()}</td><td>{f.sequence}</td><td>{f.dlc}</td><td><code>{f.rtr ? "RTR" : f.data.match(/../g)?.join(" ")}</code></td></tr>)}
      </tbody></table></div></section>}
    <details className="can-library-details">
    <summary>DBC library · {snapshot?.dbc_library?.files.length ?? 0} files{snapshot?.dbc_library?.conflicts.length ? ` · ${snapshot.dbc_library.conflicts.length} conflicting IDs` : ""}</summary>
    <div className="can-dbc">
      <div><strong>Project DBC library</strong>
        {snapshot?.dbc_library && <><p>Place your .dbc files in this folder on the server laptop:</p>
          <code className="can-dbc-path">{snapshot.dbc_library.folder}</code>
          <p>Files reload automatically within a few seconds. Shared by all devices.</p></>}
        <p>{snapshot?.dbc_library?.files.length ? `${snapshot.dbc_library.files.filter(f => f.status === "loaded").length} files loaded · ${snapshot.dbc_library.messages} unambiguous message definitions`
          : snapshot?.dbc?.filename ? `Previously uploaded DBC: ${snapshot.dbc.filename}`
          : "No DBC loaded. Raw CAN IDs and bytes remain available."}</p></div>
      {user?.role === "admin" && <label> {busy ? "Saving…" : "Add DBC files"}
        <input aria-label="Load DBC files" type="file" accept=".dbc" multiple disabled={busy}
          onChange={e => { void upload(Array.from(e.target.files || [])); e.target.value = ""; }} />
        <small>2 MiB per file. Same filename replaces that file.</small>
      </label>}
    </div>
    {snapshot?.dbc_library?.errors.map((message, i) => <p role="alert" className="error-text" key={i}>{message}</p>)}
    {!!snapshot?.dbc_library?.files.length && <ul className="can-dbc-files">
      {snapshot.dbc_library.files.map(file => <li key={file.filename} className={file.status === "loaded" ? "" : "error-text"}>
        <strong>{file.filename}</strong> — {file.status === "loaded" ? `${file.messages} messages` : file.error || "Unable to load"}
      </li>)}
    </ul>}
    {!!snapshot?.dbc_library?.conflicts.length && <div role="alert" className="can-warning">
      <strong>Conflicting DBC definitions</strong><p>Move unused definitions out of can_dbc to decode these IDs. Their raw data remains available.</p>
      <ul>{snapshot.dbc_library.conflicts.map(c => <li key={`${c.can_id}-${c.extended}`}>
        {hexId(c)} ({c.extended ? "extended" : "standard"}): {c.files.join(", ")}
      </li>)}</ul>
    </div>}
    </details>
    {notice && <p role="status">{notice}</p>}
    <p className="can-counters">Frames saved this server session: {snapshot?.metrics.persisted ?? 0} ·
      Server dropped batches: {snapshot?.metrics.dropped_batches ?? 0} ·
      DB dropped frames: {snapshot?.metrics.database_dropped_frames ?? 0} ·
      Invalid batches: {snapshot?.metrics.invalid ?? 0}</p>
    {snapshot?.status && <p className="can-counters">Device counters since boot —
      RX missed: {snapshot.status.rx_missed} · RX overruns: {snapshot.status.rx_overruns} ·
      Queue drops: {snapshot.status.queue_drops} · Publish drops: {snapshot.status.publish_drops} ·
      Serial drops: {snapshot.status.serial_drops} · Bus errors: {snapshot.status.bus_errors}</p>}
    <CanStatistics deviceId={deviceId} />
    <p>Values use the current project DBC files, including for previously captured latest frames. Raw history is preserved.</p>
  </section>;
}

function hexId(frame: { can_id: number; extended: boolean }) { return `0x${frame.can_id.toString(16).toUpperCase().padStart(frame.extended ? 8 : 3, "0")}`; }
