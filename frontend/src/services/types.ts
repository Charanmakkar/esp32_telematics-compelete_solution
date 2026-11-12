export type Channels = Record<`analog_${number}`, number>;
export interface Telemetry {
  schema_version: number;
  device_id: string;
  boot_id: string;
  sequence: number;
  timestamp_ms: number | null;
  time_valid: boolean;
  uptime_ms: number;
  channels: Channels;
  raw: number[];
  valid_mask: number;
  mqtt_connected: boolean;
  dropped_samples: number;
  source: "hardware" | "simulator";
  stale: boolean;
  received_at?: string;
  persisted_at?: string;
  id?: number;
}
export interface User {
  username: string;
  role: "admin" | "viewer";
  must_change_password: boolean;
}
export interface AuthResponse {
  user: User;
  csrf_token: string;
}
export interface Device {
  device_id: string;
  name?: string;
  online?: boolean;
  fresh?: boolean;
  last_seen?: string | null;
  last_received_at?: string | null;
  last_persisted_at?: string | null;
  source?: string;
  controls?: { A?: number | null; B?: number | null };
  mapping?: { channel: string; label: string; physical: string }[];
}
export interface Health {
  status?: string;
  mqtt_connected?: boolean;
  database?: string | boolean;
  database_connected?: boolean;
  metrics?: {
    received?: number;
    persisted?: number;
    invalid?: number;
    dropped?: number;
    duplicates?: number;
    queue_depth?: number;
    database_errors?: number;
    frequency_hz?: number;
    last_received_at?: string;
    last_persisted_at?: string;
  };
  received?: number;
  persisted?: number;
  invalid?: number;
  dropped?: number;
  duplicates?: number;
  queue_depth?: number;
  database_errors?: number;
  frequency_hz?: number;
  [key: string]: unknown;
}
export interface LatestResponse {
  received: Telemetry | null;
  persisted: Telemetry | null;
}
export interface HistoryPoint {
  timestamp_ms: number;
  value: number | null;
  min?: number | null;
  max?: number | null;
  count?: number;
}
export interface ChannelHistory {
  points: HistoryPoint[];
  stats: {
    min: number | null;
    max: number | null;
    avg: number | null;
    count: number;
  };
  downsampled?: boolean;
}
export type CommandStatus =
  | "pending"
  | "accepted"
  | "applied"
  | "rejected"
  | "timed_out"
  | "timeout"
  | "failed";
export interface Command {
  command_id: string;
  device_id: string;
  key: "A" | "B";
  value: 0 | 1;
  status: CommandStatus;
  reason?: string | null;
  created_at?: string;
  updated_at?: string;
}
export interface LiveEvent {
  type: string;
  stage?: "received" | "persisted";
  data?: Telemetry | Command | Health;
  telemetry?: Telemetry;
  received_at?: string;
  persisted_at?: string;
  [key: string]: unknown;
}
