import { useEffect, useState } from "react";
import { request } from "../services/api";
import { SW_VERSION, SW_BUILD_ID } from "../sw_version";

type VersionStatus = {
  available: boolean;
  age_seconds?: number;
  device?: { sw_version?: string | null; sw_build?: string | null };
};

export function SoftwareVersion({ deviceId }: { deviceId: string }) {
  const [status, setStatus] = useState<VersionStatus | null>(null);
  const [unreachable, setUnreachable] = useState(false);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    setStatus(null);
    setUnreachable(false);
    async function poll() {
      try {
        const next = await request<VersionStatus>(`/api/v1/can/statistics?device_id=${encodeURIComponent(deviceId)}`, { signal: controller.signal });
        if (active) { setStatus(next); setUnreachable(false); }
      } catch { if (active) setUnreachable(true); }
      if (active) timer = setTimeout(poll, 5000);
    }
    void poll();
    return () => { active = false; controller.abort(); clearTimeout(timer); };
  }, [deviceId]);
  const firmware = status?.available ? status.device?.sw_version : null;
  const stale = unreachable || (status?.age_seconds ?? Infinity) > 5;
  const differs = firmware && (firmware !== SW_VERSION || status?.device?.sw_build !== SW_BUILD_ID);
  return <div className="software-versions" aria-label="Software versions">
    <span title={`GUI build ${SW_BUILD_ID}`}>GUI <strong>v{SW_VERSION}</strong></span>
    <span title={status?.device?.sw_build ? `Reported by ${deviceId}; build ${status.device.sw_build}` : deviceId}>
      ESP32 <strong>{firmware ? `v${firmware}` : "Not reported"}</strong>
      {firmware && stale && <em>Last seen</em>}
    </span>
    {firmware && !stale && <span className={differs ? "version-different" : "version-match"}>
      {differs ? "Versions differ" : "Versions match"}
    </span>}
  </div>;
}
