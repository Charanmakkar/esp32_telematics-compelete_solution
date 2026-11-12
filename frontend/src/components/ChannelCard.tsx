import { ArrowUpRight, CheckCircle2, CircleDashed } from "lucide-react";
import { Link } from "react-router-dom";
import {
  TelemetryChart,
  channelColors,
  type PlotPoint,
} from "../charts/TelemetryChart";
import { age, channelKey, channelName, numeric } from "../services/format";
import type { Telemetry } from "../services/types";
import { channelMapping } from "../services/config";

export function ChannelCard({
  channel,
  received,
  persisted,
  data,
  mapping,
  now,
}: {
  channel: number;
  received: Telemetry | null;
  persisted: Telemetry | null;
  data: PlotPoint[];
  mapping?: string;
  now: number;
}) {
  const key = channelKey(channel);
  const valid = !!received && !!(received.valid_mask & (1 << (channel - 1)));
  const persistedValid =
    !!persisted && !!(persisted.valid_mask & (1 << (channel - 1)));
  return (
    <Link
      to={`/analytics/analog-${channel}`}
      className="channel-card"
      style={
        { "--channel-color": channelColors[channel - 1] } as React.CSSProperties
      }
    >
      <div className="channel-card-heading">
        <span className="channel-index">
          CH {String(channel).padStart(2, "0")}
        </span>
        <ArrowUpRight size={16} />
      </div>
      <h3>{channelName(channel)}</h3>
      <p className="channel-mapping" title={mapping || channelMapping(channel)}>
        {mapping || channelMapping(channel)}
      </p>
      <div className="channel-value">
        {numeric(valid ? received?.channels[key] : null)}
        <span>mV</span>
      </div>
      <TelemetryChart data={data} channels={[channel]} height={42} compact />
      <div className="channel-card-footer">
        <span className={valid ? "valid-label" : "muted-label"}>
          {valid ? <CheckCircle2 size={12} /> : <CircleDashed size={12} />}
          {valid ? "Valid signal" : "Unavailable"}
        </span>
        <span>{age(received?.received_at, now)}</span>
      </div>
      <div className="persisted-line">
        <span>Persisted</span>
        <strong>
          {numeric(persistedValid ? persisted?.channels[key] : null)} mV
        </strong>
      </div>
    </Link>
  );
}
