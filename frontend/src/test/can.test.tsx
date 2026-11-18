import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { CanPage } from "../pages/CanPage";
const mocks = vi.hoisted(() => ({ request: vi.fn(), role: "admin" }));
vi.mock("../services/api", () => ({ request: mocks.request }));
vi.mock("../hooks/useTelemetry", () => ({ useTelemetry: () => ({ deviceId: "ESP32_001" }) }));
vi.mock("../hooks/useAuth", () => ({ useAuth: () => ({ user: { role: mocks.role } }) }));
const data = { frames: [{ can_id: 291, extended: false, rtr: false, dlc: 2, data: "D204", sequence: 1,
  uptime_ms: 1, timestamp_ms: 0, received_at: new Date().toISOString(), frame_count: 3,
  message_name: "Engine", decode_status: "decoded", signals: [{ name: "Speed", value: 123.4, unit: "km/h" }] }],
  has_more: false, dbc: { filename: "engine.dbc" }, status: null, metrics: { persisted: 3 } };
beforeEach(() => { mocks.request.mockReset(); mocks.role = "admin"; });
it("shows raw ID, bytes and decoded signals with history", async () => {
  mocks.request.mockResolvedValue(data);
  render(<CanPage />);
  expect(await screen.findByText("0x123")).toBeInTheDocument();
  expect(screen.getByText("D2 04")).toBeInTheDocument();
  expect(screen.getByText("Speed")).toBeInTheDocument();
  mocks.request.mockResolvedValueOnce({ frames: data.frames });
  fireEvent.click(screen.getByText("View"));
  expect(await screen.findByText("Recent history: 0x123")).toBeInTheDocument();
});
it("shows empty capture honestly without a DBC", async () => {
  mocks.role = "viewer";
  mocks.request.mockResolvedValue({ ...data, frames: [], dbc: null });
  render(<CanPage />);
  expect(await screen.findByText(/No CAN frames recorded/)).toBeInTheDocument();
  expect(screen.queryByLabelText("Load DBC files")).not.toBeInTheDocument();
});
it("reports upload failures and retains existing data", async () => {
  mocks.request.mockResolvedValue(data);
  render(<CanPage />);
  await screen.findByText("0x123");
  const file = new File(["bad"], "invalid.dbc");
  Object.defineProperty(file, "text", { value: async () => "bad" });
  mocks.request.mockRejectedValueOnce(new Error("Invalid DBC"));
  fireEvent.change(screen.getByLabelText("Load DBC files"), { target: { files: [file] } });
  await waitFor(() => expect(screen.getByText("invalid.dbc: Invalid DBC")).toBeInTheDocument());
  expect(screen.getByText("0x123")).toBeInTheDocument();
});

it("shows the folder, loaded files, errors and conflicting definitions", async () => {
  mocks.request.mockResolvedValue({ ...data, dbc_library: { folder: "C:/Project/can_dbc", messages: 1, errors: [],
    files: [{ filename: "engine.dbc", status: "loaded", messages: 1 }, { filename: "bad.dbc", status: "error", messages: 0, error: "Invalid or unreadable DBC" }],
    conflicts: [{ can_id: 291, extended: false, files: ["engine.dbc", "duplicate.dbc"] }] } });
  render(<CanPage />);
  expect(await screen.findByText("C:/Project/can_dbc")).toBeInTheDocument();
  expect(screen.getByText("Conflicting DBC definitions")).toBeInTheDocument();
  expect(screen.getByText(/Invalid or unreadable DBC/)).toBeInTheDocument();
});

it("saves multiple files even when one file is invalid", async () => {
  mocks.request.mockImplementation((url: string, options?: { body: string }) => {
    if (url === "/api/v1/can/dbc/files") {
      return JSON.parse(options!.body).filename === "bad.dbc" ? Promise.reject(new Error("Invalid DBC")) : Promise.resolve({ messages: 3 });
    }
    return Promise.resolve(data);
  });
  render(<CanPage />);
  await screen.findByText("0x123");
  const files = ["bad.dbc", "good.dbc"].map(name => {
    const file = new File(["test"], name);
    Object.defineProperty(file, "text", { value: async () => "test" });
    return file;
  });
  expect(screen.getByLabelText("Load DBC files")).toHaveAttribute("multiple");
  fireEvent.change(screen.getByLabelText("Load DBC files"), { target: { files } });
  expect(await screen.findByText("bad.dbc: Invalid DBC good.dbc: saved 3 message definitions.")).toBeInTheDocument();
  expect(mocks.request.mock.calls.filter(([url]) => url === "/api/v1/can/dbc/files")).toHaveLength(2);
});
