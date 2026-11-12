import { useEffect, useState } from "react";
import {
  ArrowUpRight,
  CircleCheck,
  Clock3,
  LockKeyhole,
  Power,
  Radio,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { useTelemetry } from "../hooks/useTelemetry";
import { api } from "../services/api";
import { dateTime } from "../services/format";
import type { Command } from "../services/types";
import { StatusBadge } from "../components/StatusBadge";

export function ControlsPage() {
  const { user } = useAuth();
  const { deviceId, device, commands, addCommand, health, received } =
    useTelemetry();
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const pending = commands.filter(
    (command) => command.status === "pending" || command.status === "accepted",
  );
  const pendingIds = pending.map((command) => command.command_id).join(",");
  useEffect(() => {
    if (!pendingIds) return;
    let active = true;
    const ids = pendingIds.split(",");
    const timer = window.setInterval(() => {
      ids.forEach((id) =>
        api
          .commandStatus(id)
          .then((command) => {
            if (active) addCommand(command);
          })
          .catch(() => {}),
      );
    }, 1500);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [pendingIds, addCommand]);
  async function send(key: "A" | "B", value: 0 | 1) {
    setBusy(key);
    setErrors((current) => ({ ...current, [key]: "" }));
    try {
      addCommand(await api.command(deviceId, key, value));
    } catch (err) {
      setErrors((current) => ({
        ...current,
        [key]:
          err instanceof Error
            ? err.message
            : "Command could not be submitted.",
      }));
    } finally {
      setBusy(null);
    }
  }
  const canControl = user?.role === "admin" && !user.must_change_password;
  const online = !!device?.online && !!health?.mqtt_connected;
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="heading-row">
            <h1>Device controls</h1>
            <StatusBadge state="neutral">
              <ShieldCheck size={12} />
              Admin access
            </StatusBadge>
          </div>
          <p>Two independent controls, with acknowledgement from the device.</p>
        </div>
      </div>
      <div className="notice info">
        <LockKeyhole size={18} />
        <span>
          <strong>Device outputs:</strong> A → GPIO25 · B → GPIO26. Outputs
          start OFF and return OFF after a disconnect or a 60-second command
          lease. Applied status requires device acknowledgement.
        </span>
      </div>
      {received?.source === "simulator" && (
        <div className="notice simulator">
          <Radio size={17} />
          <span>
            <strong>Simulator connected.</strong> Acknowledgements come from the
            simulator; these commands do not switch physical GPIO outputs.
          </span>
        </div>
      )}
      {!canControl && (
        <div className="notice warning">
          <TriangleAlert size={17} />
          <span>
            {user?.must_change_password
              ? "Change your initial password before sending commands."
              : "An administrator account is required to send commands."}
          </span>
          {user?.must_change_password && (
            <Link to="/account">
              Update password
              <ArrowUpRight size={13} />
            </Link>
          )}
        </div>
      )}
      {!online && (
        <div className="notice warning">
          <Radio size={17} />
          <span>
            Commands are unavailable until the MQTT broker and device are
            online. Last confirmed states are shown as unknown while
            disconnected.
          </span>
        </div>
      )}
      <div className="control-grid">
        {(["A", "B"] as const).map((key) => {
          const latest = commands.find((command) => command.key === key);
          const isPending = pending.some((command) => command.key === key);
          const state = online ? device?.controls?.[key] : null;
          return (
            <section className="panel control-panel" key={key}>
              <div className="control-panel-top">
                <span className="control-letter">{key}</span>
                <StatusBadge
                  state={
                    state === 1 ? "good" : state === 0 ? "neutral" : "warning"
                  }
                >
                  {state === 1
                    ? "Confirmed ON"
                    : state === 0
                      ? "Confirmed OFF"
                      : "State unknown"}
                </StatusBadge>
              </div>
              <h2>
                Control {key}{" "}
                <span className="control-pin">GPIO{key === "A" ? 25 : 26}</span>
              </h2>
              <p>
                Send a binary state to {deviceId}.<br />
                Device acknowledgement is required.
              </p>
              <div className="control-buttons">
                <button
                  className={`button ${state === 0 ? "confirmed" : "secondary"}`}
                  disabled={!canControl || !online || isPending || busy === key}
                  onClick={() => void send(key, 0)}
                >
                  <Power size={17} />
                  OFF<span>{key} = 0</span>
                </button>
                <button
                  className={`button ${state === 1 ? "confirmed on" : "secondary"}`}
                  disabled={!canControl || !online || isPending || busy === key}
                  onClick={() => void send(key, 1)}
                >
                  <Power size={17} />
                  ON<span>{key} = 1</span>
                </button>
              </div>
              {errors[key] && (
                <div className="form-error" role="alert">
                  {errors[key]}
                </div>
              )}
              <div className="control-ack">
                <span>
                  {isPending || busy === key ? (
                    <Clock3 size={17} />
                  ) : latest?.status === "applied" ? (
                    <CircleCheck size={17} />
                  ) : (
                    <ShieldCheck size={17} />
                  )}
                </span>
                <div>
                  <strong>
                    {busy === key
                      ? "Submitting command…"
                      : isPending
                        ? "Awaiting device acknowledgement"
                        : latest
                          ? statusLabel(latest.status)
                          : "Ready for a verified command"}
                  </strong>
                  <small>
                    {latest
                      ? latest.reason ||
                        `Last request: ${key} = ${latest.value}`
                      : "Publication alone does not confirm application."}
                  </small>
                </div>
              </div>
            </section>
          );
        })}
      </div>
      <section className="panel command-history">
        <div className="panel-heading">
          <div>
            <h2>Command activity</h2>
            <p>Recorded requests and device-confirmed results</p>
          </div>
          <span className="mini-label">LATEST {commands.length}</span>
        </div>
        {commands.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Command</th>
                  <th>Requested state</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {commands.map((command) => (
                  <tr key={command.command_id}>
                    <td>
                      <strong>{command.command_id.slice(0, 8)}</strong>
                      <small>{command.device_id}</small>
                    </td>
                    <td>
                      <span className="command-value">
                        {command.key} = {command.value}
                      </span>
                    </td>
                    <td>
                      <StatusBadge
                        state={
                          command.status === "applied"
                            ? "good"
                            : command.status === "rejected" ||
                                command.status === "timed_out" ||
                                command.status === "failed"
                              ? "bad"
                              : "warning"
                        }
                      >
                        {statusLabel(command.status)}
                      </StatusBadge>
                    </td>
                    <td>{dateTime(command.created_at)}</td>
                    <td className="command-reason">{command.reason || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="command-empty">
            <ShieldCheck size={25} />
            <h3>No commands yet</h3>
            <p>Your verified command history will appear here.</p>
          </div>
        )}
      </section>
    </>
  );
}
export function statusLabel(status: Command["status"]) {
  return {
    pending: "Pending",
    accepted: "Accepted · awaiting application",
    applied: "Applied",
    rejected: "Rejected",
    timed_out: "Timed out",
    timeout: "Timed out",
    failed: "Failed",
  }[status];
}
