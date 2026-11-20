import { useEffect, useRef, useState } from "react";
import { Cpu, Upload, Wifi } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { useTelemetry } from "../hooks/useTelemetry";
import { request } from "../services/api";
import "../styles/ota.css";

type ImageInfo = { upload_id: string; filename: string; version: string; size: number; image_sha256: string };
type OtaStatus = {
  device_id: string; fresh: boolean; age_seconds: number | null; busy: boolean;
  chip: { version: string; build: string; image_sha256: string; boot_id: string; partition: string; confirmed: boolean; state: string;
    ip_address?: string; wifi_rssi_dbm?: number; uptime_ms?: number; slot_size?: number; mqtt_tls?: boolean } | null;
  limits?: { max_application_bytes: number; max_upload_bytes: number };
  transport?: { server_mqtt_tls: boolean };
  prepared: ImageInfo | null;
  job: { id: string; state: string; progress: number; message: string; image: ImageInfo } | null;
};

export function OtaPage() {
  const { deviceId } = useTelemetry();
  const { user } = useAuth();
  const [status, setStatus] = useState<OtaStatus | null>(null);
  const [error, setError] = useState("");
  const [fileFeedback, setFileFeedback] = useState("");
  const [fileRejected, setFileRejected] = useState(false);
  const [unreachable, setUnreachable] = useState(false);
  const [working, setWorking] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [dragging, setDragging] = useState(false);
  const selection = useRef(deviceId);
  selection.current = deviceId;
  const current = status?.device_id === deviceId ? status : null;
  const admin = user?.role === "admin" && !user.must_change_password;
  const ready = admin && current?.fresh && current.chip?.confirmed && current.chip.state === "idle" && !current.busy && !unreachable && !fileRejected;
  useEffect(() => setAccepted(false), [current?.prepared?.upload_id]);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    setStatus(null); setError(""); setFileFeedback(""); setFileRejected(false); setAccepted(false); setWorking(false); setDragging(false);
    async function poll() {
      try {
        const next = await request<OtaStatus>(`/api/v1/ota?device_id=${encodeURIComponent(deviceId)}`, { signal: controller.signal });
        if (active) { setStatus(next); setUnreachable(false); }
      } catch { if (active) setUnreachable(true); }
      if (active) timer = setTimeout(poll, 1000);
    }
    void poll();
    return () => { active = false; controller.abort(); clearTimeout(timer); };
  }, [deviceId]);

  async function upload(file?: File) {
    if (!file) return;
    const selected = deviceId;
    setError(""); setFileFeedback(`Checking ${file.name}…`); setFileRejected(true); setAccepted(false); setWorking(true);
    try {
      if (!/\.(bin|hex)$/i.test(file.name)) throw new Error("Choose an application .bin or .hex file.");
      if (file.size > (current?.limits?.max_upload_bytes ?? 6 * 1024 * 1024)) throw new Error("Choose a file no larger than 6 MiB.");
      await request<ImageInfo>(`/api/v1/ota/image?device_id=${encodeURIComponent(selected)}&filename=${encodeURIComponent(file.name)}`, {
        method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: file,
      });
      if (selection.current === selected) { setFileFeedback(`File accepted: ${file.name}`); setFileRejected(false); }
    } catch (e) { if (selection.current === selected) { setFileFeedback(`File not accepted: ${file.name}`); setError(e instanceof Error ? e.message : "Upload failed"); } }
    finally { if (selection.current === selected) setWorking(false); }
  }
  async function start() {
    if (!current?.prepared || !ready || !accepted) return;
    const selected = deviceId;
    setWorking(true); setError("");
    try {
      await request("/api/v1/ota/start", { method: "POST", body: JSON.stringify({ device_id: selected, upload_id: current.prepared.upload_id }) });
      if (selection.current === selected) setAccepted(false);
    } catch (e) { if (selection.current === selected) setError(e instanceof Error ? e.message : "Update could not start"); }
    finally { if (selection.current === selected) setWorking(false); }
  }
  const chip = current?.chip;
  const canUpload = admin && !working && !current?.busy;
  const maxApplication = Math.min(current?.limits?.max_application_bytes ?? 1984 * 1024, chip?.slot_size || Infinity);
  const uptimeSeconds = chip?.uptime_ms === undefined ? null : Math.floor(chip.uptime_ms / 1000);
  const uptime = uptimeSeconds === null ? "Not reported" : `${Math.floor(uptimeSeconds / 3600)}h ${Math.floor(uptimeSeconds % 3600 / 60)}m ${uptimeSeconds % 60}s`;
  const encrypted = (value?: boolean) => value === undefined ? "Not reported" : value ? "TLS encrypted" : "Unencrypted";
  return <section className="ota-page">
    <div className="page-heading"><div><div className="heading-row"><h1>OTA over Wi-Fi</h1><Wifi size={24} /></div>
      <p>Upload firmware, update your ESP32, and confirm what is actually running on the chip.</p></div></div>
    {unreachable && <p className="notice warning" role="alert">Device status cannot be refreshed. Displayed values are from the last report.</p>}
    {!admin && <p className="notice info">An administrator with a changed password can upload and install firmware.</p>}
    <div className="ota-summary" aria-label="Chip status summary">
      <article><span>Installed version</span><strong>{chip ? `v${chip.version}` : "Not reported"}</strong></article>
      <article><span>IP address</span><strong>{chip?.ip_address ?? "Not reported"}</strong></article>
      <article><span>Wi-Fi signal</span><strong>{chip?.wifi_rssi_dbm === undefined ? "Not reported" : `${chip.wifi_rssi_dbm} dBm`}</strong></article>
      <article><span>Uptime</span><strong>{uptime}</strong></article>
    </div>
    {chip && (!current?.fresh || unreachable) && <p className="ota-note">Connection details above are from the last chip report.</p>}
    <div className="ota-grid">
      <article className="ota-card">
        <h2><Cpu size={20} /> Running on {deviceId}</h2>
        <span className={`ota-state ${current?.fresh && !unreachable ? "live" : ""}`}>
          {chip ? current?.fresh && !unreachable ? "Live report from chip" : "Last seen — device not confirmed online" : "Waiting for OTA-capable firmware"}
        </span>
        {chip ? <dl><dt>Build</dt><dd>{chip.build}</dd><dt>Boot ID</dt><dd>{chip.boot_id}</dd>
          <dt>Running slot</dt><dd>{chip.partition}</dd><dt>Startup check</dt><dd>{chip.confirmed ? "Passed" : "Awaiting confirmation"}</dd>
          <dt>Image fingerprint (SHA-256)</dt><dd className="ota-hash">{chip.image_sha256}</dd></dl> :
          <p>The first OTA installation requires a USB firmware and partition update. Your existing firmware version remains visible above.</p>}
        <p className="ota-note">These values come from the running firmware on the ESP32, independently of the GUI version and uploaded file.</p>
      </article>
      <article className="ota-card">
        <h2><Upload size={20} /> Choose firmware</h2>
        <p>Use a NavSphere application <strong>.bin</strong> or application-only Intel <strong>.hex</strong> with OTA support.</p>
        <label className={`ota-upload ${dragging ? "dragging" : ""}`} data-testid="firmware-drop-zone"
          onDragOver={e => { e.preventDefault(); if (canUpload) setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={e => {
            e.preventDefault(); setDragging(false);
            if (!canUpload) return;
            if (e.dataTransfer.files.length !== 1) { setError("Drop one firmware file at a time."); setFileRejected(true); setAccepted(false); return; }
            void upload(e.dataTransfer.files[0]);
          }}>
          <strong>Choose a firmware file or drop it here</strong>
          <span>ESP32 application · .bin or Intel .hex</span>
          <input key={deviceId} aria-label="Firmware file" type="file" accept=".bin,.hex" disabled={!canUpload}
            onClick={e => { e.currentTarget.value = ""; }} onChange={e => { void upload(e.target.files?.[0]); }} />
        </label>
        {fileFeedback && <p role="status">{fileFeedback}</p>}
        {error && <p className="error-text" role="alert">{error}</p>}
        <p className="ota-note">Maximum application: {(maxApplication / 1024).toFixed(0)} KiB. Upload limit: {((current?.limits?.max_upload_bytes ?? 6 * 1024 * 1024) / 1024 / 1024).toFixed(0)} MiB, including HEX text.</p>
        {current?.prepared && !fileRejected && <dl><dt>Selected image</dt><dd>{current.prepared.filename}</dd><dt>Target version</dt><dd>v{current.prepared.version}</dd>
          <dt>Size</dt><dd>{(current.prepared.size / 1024).toFixed(1)} KiB</dd><dt>Target fingerprint</dt><dd className="ota-hash">{current.prepared.image_sha256}</dd></dl>}
        <label className="ota-consent"><input type="checkbox" checked={accepted} disabled={!ready || working || !current?.prepared} onChange={e => setAccepted(e.target.checked)} />
          Controls and CAN transmission are OFF, diagnostics are closed, and this device may reboot. Live CAN uploads pause during transfer; telemetry pauses at reboot.</label>
        <button className="primary-button" disabled={!ready || working || !current?.prepared || !accepted} onClick={() => void start()}>
          {working ? "Processing…" : "Install firmware over Wi-Fi"}</button>
        <p className="ota-note">The chip checks that controls and diagnostics are idle before accepting an update. Keep its power connected.</p>
      </article>
    </div>
    <article className="ota-card ota-guide">
      <h2>Before you upload</h2>
      <ol>
        <li><strong>Build for this board</strong><p>Use classic ESP32 NavSphere firmware with OTA support and the existing OTA partition layout.</p></li>
        <li><strong>Select an application BIN or HEX</strong><p>HEX is checked and converted by the server. Bootloaders, partition tables, full-flash bundles and firmware for other chips are rejected.</p></li>
        <li><strong>Keep power connected</strong><p>Turn controls and CAN transmission OFF and close diagnostics. The chip verifies the image, restarts, then reports its actual running version.</p></li>
      </ol>
      <p className="ota-note">Keep OTA support in future builds. The first installation needs the USB migration described in the project’s OTA guide.</p>
    </article>
    <aside className="ota-security" aria-label="Connection security">
      <strong>Connection security</strong>
      <span>Browser: {location.protocol === "https:" ? "HTTPS encrypted" : "HTTP unencrypted"}</span>
      <span>Server MQTT: {encrypted(current?.transport?.server_mqtt_tls)}</span>
      <span>Device MQTT: {encrypted(chip?.mqtt_tls)}{chip && (!current?.fresh || unreachable) ? " (last reported)" : ""}</span>
      <p>Use a trusted network for unencrypted connections. Production deployments should use HTTPS and MQTT TLS. Firmware updates require your existing administrator login.</p>
    </aside>
    {current?.job && <article className="ota-card ota-progress" aria-live="polite">
      <h2>{current.job.state === "confirmed" ? "Update confirmed by chip" : `Update: ${current.job.state}`}</h2>
      <p>{current.job.message}</p>
      <progress aria-label="Firmware transfer progress" max={100} value={current.job.progress} />
      <p>{current.job.progress}% transferred · Target v{current.job.image.version}</p>
      <p className="ota-note">100% transfer is followed by a reboot check. Success requires a new boot ID and the expected fingerprint in a live chip report.</p>
    </article>}
  </section>;
}
