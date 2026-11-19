import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { CanTransmit } from "../components/CanTransmit";
const mocks = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../services/api", () => ({ request: mocks.request }));
const off = { supported: true, fresh: true, clock_ready: true, mode: "listen_only", profiles: [
  { can_id: 0x014, data: "006000", dlc: 3, period_ms: 100 },
  { can_id: 0x548, data: "0000000000000008", dlc: 8, period_ms: 10 },
], state: { enabled: false, reason: "off", sent_014: 0, sent_548: 0, failures: 0, skipped: 0 } };
beforeEach(() => { mocks.request.mockReset(); mocks.request.mockResolvedValue(off); });
afterEach(() => { vi.useRealTimers(); });
it("shows exact frames and waits for device confirmation before displaying ON", async () => {
  render(<CanTransmit deviceId="ESP32_001" canControl />);
  expect(await screen.findByText("Transmission OFF")).toBeInTheDocument();
  expect(screen.getByText("0x548")).toBeInTheDocument();
  expect(screen.getByText("00 60 00")).toBeInTheDocument();
  let resolve!: (value: unknown) => void;
  mocks.request.mockImplementationOnce(() => new Promise(done => { resolve = done; }));
  fireEvent.click(screen.getByRole("button", { name: "Turn transmission ON" }));
  expect(screen.getByText("Waiting for ESP32 confirmation…")).toBeInTheDocument();
  expect(screen.queryByText("Transmission ON")).not.toBeInTheDocument();
  expect(JSON.parse(mocks.request.mock.calls.at(-1)![1].body)).toEqual({ device_id: "ESP32_001", enabled: true });
  await act(async () => { resolve({ ...off, state: { ...off.state, enabled: true } }); });
  expect(screen.getByText("Transmission ON")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Turn transmission OFF" }));
  expect(await screen.findByText("Transmission OFF")).toBeInTheDocument();
});
it("allows OFF but never ON using stale status", async () => {
  mocks.request.mockResolvedValue({ ...off, fresh: false });
  render(<CanTransmit deviceId="ESP32_001" canControl />);
  const stop = await screen.findByRole("button", { name: "Turn transmission OFF" });
  expect(screen.queryByRole("button", { name: "Turn transmission ON" })).not.toBeInTheDocument();
  fireEvent.click(stop);
  expect(JSON.parse(mocks.request.mock.calls.at(-1)![1].body).enabled).toBe(false);
  await act(async () => {});
});
it("reports failed commands without claiming ON", async () => {
  render(<CanTransmit deviceId="ESP32_001" canControl />);
  await screen.findByText("Transmission OFF");
  mocks.request.mockRejectedValueOnce(new Error("ESP32 confirmation timed out"));
  fireEvent.click(screen.getByRole("button", { name: "Turn transmission ON" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("ESP32 confirmation timed out");
  expect(screen.getByText("Transmission state unknown")).toBeInTheDocument();
});
it("does not expose transmission control to viewers", async () => {
  render(<CanTransmit deviceId="ESP32_001" canControl={false} />);
  await screen.findByText("Transmission OFF");
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});
it("waits for the ESP32 clock before allowing ON", async () => {
  mocks.request.mockResolvedValue({ ...off, clock_ready: false });
  render(<CanTransmit deviceId="ESP32_001" canControl />);
  expect(await screen.findByText(/Waiting for the ESP32 clock/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Turn transmission ON" })).toBeDisabled();
});
it("shows a device-side failure and disables unsupported firmware", async () => {
  mocks.request.mockResolvedValue({ ...off, supported: false, state: { ...off.state, reason: "transmit_failed" } });
  render(<CanTransmit deviceId="ESP32_001" canControl />);
  expect(await screen.findByText(/Stopped after repeated CAN send failures/)).toBeInTheDocument();
  expect(screen.getByRole("button")).toBeDisabled();
});
