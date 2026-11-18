import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { SoftwareVersion } from "../components/SoftwareVersion";
import { SW_VERSION, SW_BUILD_ID } from "../sw_version";
const mocks = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../services/api", () => ({ request: mocks.request }));
beforeEach(() => mocks.request.mockReset());

it("shows matching GUI and device-reported versions", async () => {
  mocks.request.mockResolvedValue({ available: true, age_seconds: 0, device: { sw_version: SW_VERSION, sw_build: SW_BUILD_ID } });
  render(<SoftwareVersion deviceId="ESP32_001" />);
  expect(await screen.findByText("Versions match")).toBeInTheDocument();
  expect(screen.getAllByText(`v${SW_VERSION}`)).toHaveLength(2);
});
it("does not invent a version for legacy firmware", async () => {
  mocks.request.mockResolvedValue({ available: true, age_seconds: 0, device: {} });
  render(<SoftwareVersion deviceId="ESP32_001" />);
  await waitFor(() => expect(mocks.request).toHaveBeenCalled());
  expect(screen.getByText("Not reported")).toBeInTheDocument();
  expect(screen.queryByText("Versions match")).not.toBeInTheDocument();
});
it("shows a real mismatch and marks old observations as last seen", async () => {
  mocks.request.mockResolvedValue({ available: true, age_seconds: 0, device: { sw_version: "0.0.1", sw_build: "000000000000" } });
  const view = render(<SoftwareVersion deviceId="ESP32_001" />);
  expect(await screen.findByText("Versions differ")).toBeInTheDocument();
  mocks.request.mockResolvedValue({ available: true, age_seconds: 30, device: { sw_version: SW_VERSION, sw_build: SW_BUILD_ID } });
  view.rerender(<SoftwareVersion deviceId="ESP32_002" />);
  expect(await screen.findByText("Last seen")).toBeInTheDocument();
  expect(screen.queryByText("Versions match")).not.toBeInTheDocument();
});
