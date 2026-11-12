import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TelemetryProvider, useTelemetry } from "../hooks/useTelemetry";
import type { Telemetry } from "../services/types";

const mocks = vi.hoisted(() => ({
  devices: vi.fn(),
  latest: vi.fn(),
  health: vi.fn(),
  commands: vi.fn(),
}));
vi.mock("../services/api", () => ({
  api: mocks,
  websocketUrl: () => "ws://localhost/ws/v1/telemetry",
}));
class FakeSocket {
  static instances: FakeSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor() {
    FakeSocket.instances.push(this);
  }
  close() {
    this.onclose?.();
  }
  sendEvent(event: unknown) {
    this.onmessage?.({ data: JSON.stringify(event) });
  }
}
function Probe() {
  const t = useTelemetry();
  return (
    <>
      <span data-testid="received">{t.received?.sequence ?? "none"}</span>
      <span data-testid="persisted">{t.persisted?.sequence ?? "none"}</span>
      <span data-testid="samples">{t.samples.length}</span>
      <span data-testid="connection">{t.connection}</span>
    </>
  );
}
beforeEach(() => {
  FakeSocket.instances = [];
  vi.stubGlobal("WebSocket", FakeSocket);
  mocks.devices.mockResolvedValue([{ device_id: "ESP32_001", online: true }]);
  mocks.latest.mockResolvedValue({ received: null, persisted: null });
  mocks.health.mockResolvedValue({ mqtt_connected: true });
  mocks.commands.mockResolvedValue([]);
});
describe("live transport", () => {
  it("separates received and persisted events and ignores another device", async () => {
    render(
      <TelemetryProvider>
        <Probe />
      </TelemetryProvider>,
    );
    await waitFor(() => expect(mocks.latest).toHaveBeenCalled());
    const sample = {
      device_id: "ESP32_001",
      boot_id: "boot",
      sequence: 1,
      received_at: new Date().toISOString(),
    } as Telemetry;
    const socket = FakeSocket.instances[0];
    act(() =>
      socket.sendEvent({ type: "telemetry", stage: "received", data: sample }),
    );
    expect(screen.getByTestId("received")).toHaveTextContent("1");
    expect(screen.getByTestId("persisted")).toHaveTextContent("none");
    act(() =>
      socket.sendEvent({ type: "telemetry", stage: "persisted", data: sample }),
    );
    expect(screen.getByTestId("persisted")).toHaveTextContent("1");
    act(() =>
      socket.sendEvent({
        type: "telemetry",
        stage: "received",
        data: { ...sample, device_id: "OTHER", sequence: 999 },
      }),
    );
    expect(screen.getByTestId("received")).toHaveTextContent("1");
  });
  it("deduplicates consecutive samples and bounds the live window to 600", async () => {
    render(
      <TelemetryProvider>
        <Probe />
      </TelemetryProvider>,
    );
    await waitFor(() => expect(mocks.latest).toHaveBeenCalled());
    const socket = FakeSocket.instances[0];
    act(() => {
      for (let sequence = 1; sequence <= 650; sequence++)
        socket.sendEvent({
          type: "telemetry",
          stage: "received",
          data: { device_id: "ESP32_001", boot_id: "boot", sequence },
        });
    });
    expect(screen.getByTestId("samples")).toHaveTextContent("600");
    act(() =>
      socket.sendEvent({
        type: "telemetry",
        stage: "received",
        data: { device_id: "ESP32_001", boot_id: "boot", sequence: 650 },
      }),
    );
    expect(screen.getByTestId("samples")).toHaveTextContent("600");
  });
});
