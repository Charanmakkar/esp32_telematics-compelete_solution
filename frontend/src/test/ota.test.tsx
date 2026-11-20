import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { OtaPage } from "../pages/OtaPage";
const mocks = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../services/api", () => ({ request: mocks.request }));
vi.mock("../hooks/useTelemetry", () => ({ useTelemetry: () => ({ deviceId: "ESP32_001" }) }));
vi.mock("../hooks/useAuth", () => ({ useAuth: () => ({ user: { role: "admin", must_change_password: false } }) }));
beforeEach(() => { mocks.request.mockReset(); });
it("shows chip-reported identity independently of the uploaded target", async () => {
  mocks.request.mockResolvedValue({ device_id: "ESP32_001", fresh: true, busy: false,
    chip: { version: "1.2.0", build: "chip-build", image_sha256: "chip-hash", confirmed: true, state: "idle" },
    prepared: { filename: "firmware.bin", version: "1.3.0", size: 1024, image_sha256: "target-hash" } });
  render(<OtaPage />);
  expect(await screen.findByText("v1.2.0")).toBeInTheDocument();
  expect(screen.getByText("v1.3.0")).toBeInTheDocument();
  expect(screen.getByText("chip-hash")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Install firmware over Wi-Fi" })).toBeDisabled();
});
it("never presents complete transfer as successful installation", async () => {
  mocks.request.mockResolvedValue({ device_id: "ESP32_001", fresh: false, chip: null, busy: true,
    job: { state: "rebooting", progress: 100, message: "Waiting for chip", image: { version: "1.3.0" } } });
  render(<OtaPage />);
  expect(await screen.findByText("Update: rebooting")).toBeInTheDocument();
  expect(screen.queryByText("Update confirmed by chip")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Install firmware over Wi-Fi" })).toBeDisabled();
});
it("shows real network readings, uptime, limits and transport security", async () => {
  mocks.request.mockResolvedValue({ device_id: "ESP32_001", fresh: true, busy: false,
    chip: { version: "1.3.0", ip_address: "192.168.10.60", wifi_rssi_dbm: -63,
      uptime_ms: 5408000, slot_size: 2031616, mqtt_tls: false, confirmed: true, state: "idle" },
    limits: { max_application_bytes: 2031616, max_upload_bytes: 6291456 },
    transport: { server_mqtt_tls: false } });
  render(<OtaPage />);
  expect(await screen.findByText("192.168.10.60")).toBeInTheDocument();
  expect(screen.getByText("-63 dBm")).toBeInTheDocument();
  expect(screen.getByText("1h 30m 8s")).toBeInTheDocument();
  expect(screen.getByText(/Maximum application: 1984 KiB/)).toBeInTheDocument();
  expect(screen.getByText("Server MQTT: Unencrypted")).toBeInTheDocument();
  expect(screen.getByText("Before you upload")).toBeInTheDocument();
});
it("uploads one dropped application and rejects unsupported files", async () => {
  mocks.request.mockResolvedValue({ device_id: "ESP32_001", fresh: false, busy: false, chip: null });
  render(<OtaPage />);
  await waitFor(() => expect(mocks.request).toHaveBeenCalled());
  const file = new File(["test"], "app.bin", { type: "application/octet-stream" });
  fireEvent.drop(screen.getByTestId("firmware-drop-zone"), { dataTransfer: { files: [file] } });
  await waitFor(() => expect(mocks.request).toHaveBeenCalledWith(expect.stringContaining("/ota/image?"), expect.objectContaining({ body: file })));
  await waitFor(() => expect(screen.getByLabelText("Firmware file")).not.toBeDisabled());
  const before = mocks.request.mock.calls.length;
  fireEvent.drop(screen.getByTestId("firmware-drop-zone"), { dataTransfer: { files: [new File(["test"], "app.txt")] } });
  expect(await screen.findByRole("alert")).toHaveTextContent("Choose an application .bin or .hex file.");
  expect(mocks.request.mock.calls.length).toBe(before);
});
it("ignores drops during an active update", async () => {
  mocks.request.mockResolvedValue({ device_id: "ESP32_001", fresh: false, busy: true, chip: null });
  render(<OtaPage />);
  await waitFor(() => expect(screen.getByLabelText("Firmware file")).toBeDisabled());
  const before = mocks.request.mock.calls.length;
  fireEvent.drop(screen.getByTestId("firmware-drop-zone"), { dataTransfer: { files: [new File(["test"], "app.bin")] } });
  expect(mocks.request.mock.calls.length).toBe(before);
});
it("rejects multiple dropped files", async () => {
  mocks.request.mockResolvedValue({ device_id: "ESP32_001", fresh: false, busy: false, chip: null });
  render(<OtaPage />);
  await waitFor(() => expect(mocks.request).toHaveBeenCalled());
  const before = mocks.request.mock.calls.length;
  fireEvent.drop(screen.getByTestId("firmware-drop-zone"), { dataTransfer: { files: [new File(["a"], "a.bin"), new File(["b"], "b.bin")] } });
  expect(await screen.findByRole("alert")).toHaveTextContent(/one/i);
  expect(mocks.request.mock.calls.length).toBe(before);
});
it("shows a rejected file beside the picker and prevents installing an older staged image", async () => {
  const status = { device_id: "ESP32_001", fresh: true, busy: false,
    chip: { version: "1.1.20", confirmed: true, state: "idle" },
    prepared: { upload_id: "older-upload", filename: "previous.bin", version: "1.1.21", size: 1024, image_sha256: "previous-hash" } };
  mocks.request.mockImplementation((path: string) => path.includes("/ota/image?")
    ? Promise.reject(new Error("Choose NavSphere firmware with OTA protocol 1 support; legacy images would remove OTA"))
    : Promise.resolve(status));
  render(<OtaPage />);
  await screen.findByText("previous.bin");
  fireEvent.click(screen.getByRole("checkbox"));
  expect(screen.getByRole("button", { name: "Install firmware over Wi-Fi" })).toBeEnabled();
  fireEvent.change(screen.getByLabelText("Firmware file"), { target: { files: [new File(["old"], "firmware.bin")] } });
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("legacy images would remove OTA");
  expect(screen.getByTestId("firmware-drop-zone").parentElement).toContainElement(alert);
  expect(screen.getByRole("status")).toHaveTextContent("File not accepted: firmware.bin");
  expect(screen.queryByText("previous.bin")).not.toBeInTheDocument();
  expect(screen.queryByText("Target version")).not.toBeInTheDocument();
  expect(screen.getByRole("checkbox")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Install firmware over Wi-Fi" })).toBeDisabled();
});
it("keeps accepted-file feedback visible when reopening the picker for retry", async () => {
  mocks.request.mockResolvedValue({ device_id: "ESP32_001", fresh: false, busy: false, chip: null });
  render(<OtaPage />);
  const input = screen.getByLabelText("Firmware file");
  fireEvent.change(input, { target: { files: [new File(["app"], "firmware.bin")] } });
  expect(await screen.findByText("File accepted: firmware.bin")).toBeInTheDocument();
  fireEvent.click(input);
  expect(input).toHaveValue("");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
