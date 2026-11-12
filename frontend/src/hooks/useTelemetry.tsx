import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api, websocketUrl } from "../services/api";
import type {
  Command,
  Device,
  Health,
  LiveEvent,
  Telemetry,
} from "../services/types";

interface TelemetryContextValue {
  deviceId: string;
  selectDevice: (id: string) => void;
  devices: Device[];
  device: Device | undefined;
  received: Telemetry | null;
  persisted: Telemetry | null;
  samples: Telemetry[];
  health: Health | null;
  connection: "connecting" | "connected" | "disconnected";
  loading: boolean;
  error: string;
  now: number;
  commands: Command[];
  addCommand: (command: Command) => void;
  refresh: () => Promise<void>;
}
const TelemetryContext = createContext<TelemetryContextValue | null>(null);
export function TelemetryProvider({ children }: { children: ReactNode }) {
  const [deviceId, selectDevice] = useState("ESP32_001");
  const [devices, setDevices] = useState<Device[]>([]);
  const [received, setReceived] = useState<Telemetry | null>(null);
  const [persisted, setPersisted] = useState<Telemetry | null>(null);
  const [samples, setSamples] = useState<Telemetry[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [connection, setConnection] =
    useState<TelemetryContextValue["connection"]>("connecting");
  const [commands, setCommands] = useState<Command[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [now, setNow] = useState(Date.now());
  const selection = useRef(deviceId);
  selection.current = deviceId;
  const addCommand = useCallback((command: Command) => {
    if (command.device_id !== selection.current) return;
    setCommands((current) =>
      [
        command,
        ...current.filter((item) => item.command_id !== command.command_id),
      ].slice(0, 50),
    );
    if (command.status === "applied")
      setDevices((current) =>
        current.map((item) =>
          item.device_id === command.device_id
            ? {
                ...item,
                controls: { ...item.controls, [command.key]: command.value },
              }
            : item,
        ),
      );
  }, []);
  const refresh = useCallback(async () => {
    const selected = deviceId;
    const results = await Promise.allSettled([
      api.devices(),
      api.latest(selected),
      api.health(),
      api.commands(selected),
    ]);
    if (selection.current !== selected) return;
    if (results[0].status === "fulfilled") setDevices(results[0].value);
    if (results[1].status === "fulfilled") {
      const latest = results[1].value;
      setReceived((current) => newer(current, latest.received));
      setPersisted((current) => newer(current, latest.persisted));
    }
    if (results[2].status === "fulfilled") setHealth(results[2].value);
    else setHealth(null);
    if (results[3].status === "fulfilled") setCommands(results[3].value);
    const failures = results.filter((result) => result.status === "rejected");
    setError(
      failures.length
        ? "Some services could not be reached. Values show the last confirmed state."
        : "",
    );
    setLoading(false);
  }, [deviceId]);
  useEffect(() => {
    setLoading(true);
    setReceived(null);
    setPersisted(null);
    setSamples([]);
    setCommands([]);
    void refresh();
    // Dependency health and confirmed device state change independently from live telemetry.
    const healthTimer = window.setInterval(() => {
      void refresh();
    }, 10000);
    return () => window.clearInterval(healthTimer);
  }, [refresh]);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => {
    let active = true;
    let socket: WebSocket | undefined;
    let retryTimer = 0;
    let attempt = 0;
    function connect() {
      if (!active) return;
      setConnection("connecting");
      socket = new WebSocket(websocketUrl());
      socket.onopen = () => {
        if (active) {
          attempt = 0;
          setConnection("connected");
          void refresh();
        }
      };
      socket.onmessage = (event) => {
        if (!active) return;
        try {
          const message = JSON.parse(event.data) as LiveEvent;
          if (message.type === "command" && message.data) {
            addCommand(message.data as Command);
            return;
          }
          if (message.type !== "telemetry" || !message.data) return;
          const sample = message.data as Telemetry;
          if (sample.device_id !== selection.current) return;
          if (message.stage === "persisted") {
            setPersisted(sample);
            return;
          }
          setReceived(sample);
          setSamples((current) => {
            const last = current[current.length - 1];
            if (
              last &&
              last.boot_id === sample.boot_id &&
              last.sequence === sample.sequence
            )
              return current;
            return [...current.slice(-599), sample];
          });
        } catch {
          /* An unrecognized event must not interrupt the telemetry stream. */
        }
      };
      socket.onerror = () => {
        socket?.close();
      };
      socket.onclose = () => {
        if (!active) return;
        setConnection("disconnected");
        retryTimer = window.setTimeout(
          connect,
          Math.min(30000, 1000 * 2 ** Math.min(attempt++, 5)),
        );
      };
    }
    connect();
    return () => {
      active = false;
      window.clearTimeout(retryTimer);
      socket?.close();
    };
  }, [refresh, addCommand]);
  return (
    <TelemetryContext.Provider
      value={{
        deviceId,
        selectDevice,
        devices,
        device: devices.find((item) => item.device_id === deviceId),
        received,
        persisted,
        samples,
        health,
        connection,
        loading,
        error,
        now,
        commands,
        addCommand,
        refresh,
      }}
    >
      {children}
    </TelemetryContext.Provider>
  );
}
function newer(current: Telemetry | null, incoming: Telemetry | null) {
  if (!current) return incoming;
  if (!incoming) return current;
  if (
    current.received_at &&
    incoming.received_at &&
    Date.parse(current.received_at) > Date.parse(incoming.received_at)
  )
    return current;
  return incoming;
}
export function useTelemetry() {
  const value = useContext(TelemetryContext);
  if (!value) throw new Error("TelemetryProvider is required");
  return value;
}
