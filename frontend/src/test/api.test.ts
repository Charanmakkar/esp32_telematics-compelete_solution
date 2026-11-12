import { afterEach, describe, expect, it, vi } from "vitest";
import { api, request, setCsrf } from "../services/api";

afterEach(() => {
  vi.unstubAllGlobals();
  setCsrf("");
});
describe("HTTP contract", () => {
  it("uses cookie credentials and a CSRF header for an administrative mutation", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ command_id: "x", status: "pending" }), {
          status: 200,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    setCsrf("session-csrf");
    await api.command("ESP32_001", "A", 1);
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/commands");
    expect(options.credentials).toBe("include");
    expect(options.headers.get("X-CSRF-Token")).toBe("session-csrf");
    expect(JSON.parse(options.body)).toEqual({
      device_id: "ESP32_001",
      key: "A",
      value: 1,
    });
  });
  it("normalizes server downsampled history and limits the request to 600 points", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({
            points: [{ timestamp_ms: 1000, channels: { analog_6: 2300 } }],
            statistics: {
              analog_6: { min: 100, max: 3000, avg: 2000, count: 12300 },
            },
            aggregated: true,
          }),
          { status: 200 },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    const result = await api.history("ESP32_001", 6, 1000, 2000);
    expect(fetchMock.mock.calls[0][0]).toContain("limit=600");
    expect(result.points).toEqual([{ timestamp_ms: 1000, value: 2300 }]);
    expect(result.stats.count).toBe(12300);
    expect(result.downsampled).toBe(true);
  });
  it("surfaces validation errors and signals an expired session", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ detail: "Session expired" }), {
            status: 401,
          }),
        ),
    );
    const expired = vi.fn();
    window.addEventListener("navsphere:unauthorized", expired);
    await expect(request("/api/v1/devices")).rejects.toThrow("Session expired");
    expect(expired).toHaveBeenCalledOnce();
    window.removeEventListener("navsphere:unauthorized", expired);
  });
});
