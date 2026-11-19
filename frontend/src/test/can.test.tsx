import { act, render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
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
afterEach(() => { cleanup(); vi.useRealTimers(); });
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

it("polling visibly updates raw values and keeps old runs selectable", async () => {
  vi.useFakeTimers();
  let frameData = "D204";
  mocks.request.mockImplementation((url: string) => Promise.resolve(url.includes("/statistics") ? { available: false } : {
    ...data, frames: [{ ...data.frames[0], data: frameData }], server_time: new Date().toISOString(),
  }));
  render(<CanPage />);
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  expect(screen.getByText("D2 04")).toBeInTheDocument();
  expect(mocks.request.mock.calls.some(([url]) => url.includes("current_boot_only=true"))).toBe(true);
  frameData = "D304";
  await act(async () => { await vi.advanceTimersByTimeAsync(1100); });
  expect(screen.getByText("D3 04")).toBeInTheDocument();
  expect(screen.queryByText("D2 04")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("CAN frame view"), { target: { value: "all" } });
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  expect(mocks.request.mock.calls.some(([url]) => url.includes("current_boot_only=false"))).toBe(true);
});

it("a stalled poll times out and retries while displayed ages continue advancing", async () => {
  vi.useFakeTimers();
  let polls = 0;
  mocks.request.mockImplementation((url: string, options?: RequestInit) => {
    if (url.includes("/statistics")) return Promise.resolve({ available: false });
    if (url.includes("/can/tx")) return Promise.resolve({ supported: false, fresh: false, state: null });
    polls++;
    if (polls === 1) return Promise.resolve({ ...data, server_time: data.frames[0].received_at });
    if (polls === 2) return new Promise((_, reject) => options?.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError"))));
    return Promise.resolve({ ...data, frames: [{ ...data.frames[0], data: "ABCD" }] });
  });
  render(<CanPage />);
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  await act(async () => { await vi.advanceTimersByTimeAsync(9100); });
  expect(screen.getByText(/CAN update timed out/)).toBeInTheDocument();
  expect(screen.getByText("9.0s ago")).toBeInTheDocument();
  await act(async () => { await vi.advanceTimersByTimeAsync(1100); });
  expect(screen.getByText("AB CD")).toBeInTheDocument();
});

it("searches across pages, keeps matching values live, and clears back to all IDs", async () => {
  vi.useFakeTimers();
  let raw = "D204";
  const other = { ...data.frames[0], can_id: 512, message_name: "Battery", data: "FFFF" };
  mocks.request.mockImplementation((url: string) => {
    if (url.includes("/statistics")) return Promise.resolve({ available: false });
    const params = new URL(url, "http://localhost").searchParams;
    const term = params.get("search");
    const frames = term === "missing" ? [] : term ? [{ ...data.frames[0], data: raw, dlc: raw.length / 2 }] : [data.frames[0], other];
    return Promise.resolve({ ...data, frames, has_more: !term && params.get("offset") === "0" });
  });
  render(<CanPage />);
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  fireEvent.click(screen.getByText("Next IDs"));
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  expect(screen.getByText("IDs 101–102")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Search CAN messages"), { target: { value: "D2 04" } });
  await act(async () => { await vi.advanceTimersByTimeAsync(300); });
  const latestUrl = mocks.request.mock.calls.filter(([url]) => url.includes("/latest")).slice(-1)[0][0];
  expect(latestUrl).toContain("offset=0");
  expect(latestUrl).toContain("search=D2%2004");
  expect(screen.queryByText("0x200")).not.toBeInTheDocument();
  expect(screen.getByText("Matching IDs 1–1")).toBeInTheDocument();
  raw = "D204AB";
  await act(async () => { await vi.advanceTimersByTimeAsync(1100); });
  expect(screen.getByText("D2 04 AB")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Search CAN messages"), { target: { value: "missing" } });
  await act(async () => { await vi.advanceTimersByTimeAsync(300); });
  expect(screen.getByText(/No CAN messages match/)).toBeInTheDocument();
  fireEvent.click(screen.getByText("Clear search"));
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  expect(screen.getByText("0x200")).toBeInTheDocument();
  expect(screen.getByLabelText("Search CAN messages")).toHaveValue("");
  expect(screen.getByText("CAN statistics & protocol details")).toBeInTheDocument();
});
