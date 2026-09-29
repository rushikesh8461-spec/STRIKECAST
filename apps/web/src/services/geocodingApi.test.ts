import { describe, expect, it, vi } from "vitest";
import { searchLocation } from "./geocodingApi";

describe("location search", () => {
  it("returns valid coordinates from the configured fixed geocoder", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([
      { lat: "12.97", lon: "77.59", display_name: "Bengaluru, India" },
      { lat: "not-a-number", lon: "77", display_name: "invalid" },
    ]), { status: 200, headers: { "content-type": "application/json" } })));
    await expect(searchLocation("Bengaluru")).resolves.toEqual([
      { latitude: 12.97, longitude: 77.59, displayName: "Bengaluru, India" },
    ]);
  });

  it("returns an empty result for blank queries and exposes provider errors", async () => {
    expect(await searchLocation("  ")).toEqual([]);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status: 503, headers: { "content-type": "application/json" } })));
    await expect(searchLocation("Bengaluru")).rejects.toThrow("503");
  });
});
