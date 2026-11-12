import type {
  AuthResponse,
  ChannelHistory,
  Command,
  Device,
  Health,
  LatestResponse,
} from "./types";

const base = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
let csrfToken = "";
export function setCsrf(token: string) {
  csrfToken = token;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body) headers.set("Content-Type", "application/json");
  if (options.method && options.method !== "GET" && csrfToken)
    headers.set("X-CSRF-Token", csrfToken);
  const response = await fetch(`${base}${path}`, {
    ...options,
    credentials: "include",
    headers,
  });
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok) {
    if (response.status === 401 && !path.endsWith("/auth/login"))
      window.dispatchEvent(new Event("navsphere:unauthorized"));
    const detail =
      body && typeof body === "object" && "detail" in body
        ? (body as { detail: unknown }).detail
        : null;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail
              .map((e: { msg?: string }) => e.msg || "Invalid request")
              .join("; ")
          : `Request failed (${response.status}). Please try again.`;
    throw new ApiError(response.status, message);
  }
  return body as T;
}
export const api = {
  me: () => request<AuthResponse>("/api/v1/auth/me"),
  login: (username: string, password: string) =>
    request<AuthResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  logout: () => request<void>("/api/v1/auth/logout", { method: "POST" }),
  password: (current_password: string, new_password: string) =>
    request<AuthResponse>("/api/v1/auth/password", {
      method: "POST",
      body: JSON.stringify({ current_password, new_password }),
    }),
  devices: async () =>
    (await request<{ devices: Device[] }>("/api/v1/devices")).devices,
  device: (id: string) =>
    request<Device>(`/api/v1/devices/${encodeURIComponent(id)}/status`),
  health: () => request<Health>("/api/v1/health"),
  latest: (id: string) =>
    request<LatestResponse>(
      `/api/v1/telemetry/latest?device_id=${encodeURIComponent(id)}`,
    ),
  history: async (
    id: string,
    channel: number,
    start: number,
    end: number,
    signal?: AbortSignal,
  ): Promise<ChannelHistory> => {
    const key = `analog_${channel}`;
    const data = await request<{
      points: {
        timestamp_ms: number;
        channels: Record<string, number | null>;
      }[];
      statistics: Record<string, ChannelHistory["stats"]>;
      aggregated: boolean;
    }>(
      `/api/v1/telemetry/channels/${channel}?device_id=${encodeURIComponent(id)}&start_ms=${start}&end_ms=${end}&limit=600`,
      { signal },
    );
    return {
      points: data.points.map((point) => ({
        timestamp_ms: point.timestamp_ms,
        value: point.channels[key] ?? null,
      })),
      stats: data.statistics[key] || {
        min: null,
        max: null,
        avg: null,
        count: 0,
      },
      downsampled: data.aggregated,
    };
  },
  command: (device_id: string, key: "A" | "B", value: 0 | 1) =>
    request<Command>("/api/v1/commands", {
      method: "POST",
      body: JSON.stringify({ device_id, key, value }),
    }),
  commandStatus: (id: string) =>
    request<Command>(`/api/v1/commands/${encodeURIComponent(id)}`),
  commands: async (id: string) =>
    (
      await request<{ commands: Command[] }>(
        `/api/v1/commands?device_id=${encodeURIComponent(id)}`,
      )
    ).commands,
};
export const websocketUrl = () =>
  import.meta.env.VITE_WS_URL ||
  `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/ws/v1/telemetry`;
export const documentationUrl = `${base}/docs`;
