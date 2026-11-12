import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LoginPage } from "../pages/LoginPage";
import { DashboardPage } from "../pages/DashboardPage";
import { ControlsPage } from "../pages/ControlsPage";
import { AnalyticsPage } from "../pages/AnalyticsPage";
import { AccountPage } from "../pages/AccountPage";
import type { Command, Telemetry } from "../services/types";

const mocks = vi.hoisted(() => ({
  auth: {} as Record<string, unknown>,
  telemetry: {} as Record<string, unknown>,
  command: vi.fn(),
  commandStatus: vi.fn(),
  history: vi.fn(),
}));
vi.mock("../hooks/useAuth", () => ({ useAuth: () => mocks.auth }));
vi.mock("../hooks/useTelemetry", () => ({
  useTelemetry: () => mocks.telemetry,
}));
vi.mock("../services/api", () => ({
  api: {
    command: mocks.command,
    commandStatus: mocks.commandStatus,
    history: mocks.history,
  },
}));
vi.mock("../charts/TelemetryChart", () => ({
  channelColors: Array(6).fill("#22d3ee"),
  TelemetryChart: ({ data }: { data: unknown[] }) => (
    <div aria-label="Telemetry plot">{data.length} plotted points</div>
  ),
}));

const sample: Telemetry = {
  schema_version: 1,
  device_id: "ESP32_001",
  boot_id: "boot-a",
  sequence: 15,
  timestamp_ms: Date.now(),
  time_valid: true,
  uptime_ms: 1500,
  channels: {
    analog_1: 1234,
    analog_2: 1500,
    analog_3: 1800,
    analog_4: 2000,
    analog_5: 2100,
    analog_6: 2300,
  },
  raw: [1, 2, 3, 4, 5, 6],
  valid_mask: 63,
  mqtt_connected: true,
  dropped_samples: 0,
  source: "simulator",
  stale: false,
  received_at: new Date().toISOString(),
};
function renderPage(page: React.ReactNode, path = "/") {
  return render(<MemoryRouter initialEntries={[path]}>{page}</MemoryRouter>);
}
beforeEach(() => {
  mocks.auth = {
    user: { username: "operator", role: "admin", must_change_password: false },
    loading: false,
    login: vi.fn(),
    changePassword: vi.fn(),
  };
  mocks.telemetry = {
    deviceId: "ESP32_001",
    device: { device_id: "ESP32_001", online: true, controls: { A: 0, B: 0 } },
    received: sample,
    persisted: {
      ...sample,
      sequence: 14,
      channels: { ...sample.channels, analog_1: 1200 },
    },
    samples: [sample],
    health: {
      mqtt_connected: true,
      database_connected: true,
      metrics: {
        received: 15,
        persisted: 14,
        frequency_hz: 10,
        invalid: 0,
        dropped: 0,
      },
    },
    commands: [],
    addCommand: vi.fn(),
    now: Date.now(),
    connection: "connected",
    loading: false,
    error: "",
    refresh: vi.fn(),
  };
  mocks.command.mockReset();
  mocks.commandStatus.mockReset();
  mocks.history.mockReset();
});
describe("authentication and account", () => {
  it("submits credentials and renders a backend login failure", async () => {
    mocks.auth = {
      ...mocks.auth,
      user: null,
      login: vi
        .fn()
        .mockRejectedValue(new Error("Invalid username or password")),
    };
    renderPage(<LoginPage />);
    await userEvent.type(screen.getByLabelText("Username"), "operator");
    await userEvent.type(screen.getByLabelText("Password"), "incorrect");
    await userEvent.click(
      screen.getByRole("button", { name: /Sign in to workspace/ }),
    );
    expect(mocks.auth.login).toHaveBeenCalledWith("operator", "incorrect");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid username or password",
    );
    expect(localStorage.getItem("password")).toBeNull();
  });
  it("requires matching passwords before calling the backend", async () => {
    renderPage(<AccountPage />);
    await userEvent.type(screen.getByLabelText("Current password"), "initial");
    await userEvent.type(
      screen.getByLabelText("New password"),
      "a-strong-password",
    );
    await userEvent.type(
      screen.getByLabelText("Confirm new password"),
      "different-password",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Update password" }),
    );
    expect(screen.getByRole("alert")).toHaveTextContent("do not match");
    expect(mocks.auth.changePassword).not.toHaveBeenCalled();
  });
});
describe("telemetry overview", () => {
  it("renders exactly six mapped channels and distinguishes incoming and persisted values", () => {
    renderPage(<DashboardPage />);
    const links = screen
      .getAllByRole("link")
      .filter((link) => link.classList.contains("channel-card"));
    expect(links).toHaveLength(6);
    expect(screen.getByText("GPIO39 · ADC1")).toBeInTheDocument();
    expect(screen.queryByText("Analog 07")).not.toBeInTheDocument();
    expect(within(links[0]).getByText("1,234")).toBeInTheDocument();
    expect(within(links[0]).getByText("1,200 mV")).toBeInTheDocument();
    expect(screen.getByText("Simulator session")).toBeInTheDocument();
  });
  it("marks an interrupted stream and unavailable channel without inventing a reading", () => {
    mocks.telemetry = {
      ...mocks.telemetry,
      connection: "disconnected",
      received: { ...sample, valid_mask: 62 },
    };
    renderPage(<DashboardPage />);
    const first = screen
      .getAllByRole("link")
      .find((link) => link.classList.contains("channel-card"))!;
    expect(within(first).getByText("Unavailable")).toBeInTheDocument();
    expect(within(first).queryByText("1,234")).not.toBeInTheDocument();
    expect(screen.getByText(/Live stream interrupted/)).toBeInTheDocument();
  });
});
describe("commands", () => {
  it("keeps the confirmed OFF state after a command is published pending acknowledgement", async () => {
    const pending: Command = {
      command_id: "cmd-1",
      device_id: "ESP32_001",
      key: "A",
      value: 1,
      status: "pending",
    };
    mocks.command.mockResolvedValue(pending);
    renderPage(<ControlsPage />);
    await userEvent.click(
      screen.getAllByRole("button", { name: /ON A = 1/ })[0],
    );
    expect(mocks.command).toHaveBeenCalledWith("ESP32_001", "A", 1);
    expect(mocks.telemetry.addCommand).toHaveBeenCalledWith(pending);
    expect(screen.getAllByText("Confirmed OFF")).toHaveLength(2);
    expect(screen.queryByText("Confirmed ON")).not.toBeInTheDocument();
  });
  it("renders backend command rejection and does not update confirmed state", async () => {
    mocks.command.mockRejectedValue(new Error("Device is offline"));
    renderPage(<ControlsPage />);
    await userEvent.click(screen.getByRole("button", { name: /ON A = 1/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Device is offline",
    );
    expect(mocks.telemetry.addCommand).not.toHaveBeenCalled();
  });
  it("disables commands for viewers and after disconnect", () => {
    mocks.auth = {
      ...mocks.auth,
      user: { username: "reader", role: "viewer", must_change_password: false },
    };
    renderPage(<ControlsPage />);
    expect(screen.getByRole("button", { name: /ON A = 1/ })).toBeDisabled();
  });
});
describe("channel analytics", () => {
  it("requests bounded historical data for the selected range and displays server statistics", async () => {
    mocks.history.mockResolvedValue({
      points: [{ timestamp_ms: Date.now(), value: 1220 }],
      stats: { min: 100, max: 2000, avg: 1200, count: 10000 },
      downsampled: true,
    });
    renderPage(
      <Routes>
        <Route path="/analytics/:channelId" element={<AnalyticsPage />} />
      </Routes>,
      "/analytics/analog-2",
    );
    await userEvent.click(screen.getByRole("button", { name: "Historical" }));
    await waitFor(() => expect(mocks.history).toHaveBeenCalled());
    expect(mocks.history.mock.calls[0][0]).toBe("ESP32_001");
    expect(mocks.history.mock.calls[0][1]).toBe(2);
    expect(
      await screen.findByText("10,000 valid measurements"),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "24 hours" }));
    await waitFor(() => expect(mocks.history).toHaveBeenCalledTimes(2));
    const call = mocks.history.mock.calls[1];
    expect(call[3] - call[2]).toBe(86400000);
  });
  it("rejects the seventh channel route", () => {
    renderPage(
      <Routes>
        <Route path="/analytics/:channelId" element={<AnalyticsPage />} />
      </Routes>,
      "/analytics/analog-7",
    );
    expect(
      screen.getByRole("heading", { name: "Channel not found" }),
    ).toBeInTheDocument();
    expect(mocks.history).not.toHaveBeenCalled();
  });
  it("validates a reversed custom time range", async () => {
    mocks.history.mockResolvedValue({
      points: [],
      stats: { min: null, max: null, avg: null, count: 0 },
    });
    renderPage(
      <Routes>
        <Route path="/analytics/:channelId" element={<AnalyticsPage />} />
      </Routes>,
      "/analytics/analog-1",
    );
    await userEvent.click(screen.getByRole("button", { name: "Custom" }));
    fireEvent.change(screen.getByLabelText("Range start"), {
      target: { value: "2026-11-12T12:00" },
    });
    fireEvent.change(screen.getByLabelText("Range end"), {
      target: { value: "2026-11-11T12:00" },
    });
    await userEvent.click(screen.getByRole("button", { name: "Apply range" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "start time before",
    );
  });
});
