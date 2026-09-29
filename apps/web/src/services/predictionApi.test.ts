import { beforeEach, describe, expect, it, vi } from "vitest";
import { getPrediction } from "./predictionApi";

const prediction = {
  timestamp: "2026-09-27T00:00:00Z", forecast_horizon_minutes: 60,
  latitude: 12, longitude: 77, grid_shape: null, prediction: 20,
  probability: 0.2, confidence: 0.8, model_name: "demo-model", model_version: "demo-v1",
  model_mode: "demo", data_source: "synthetic-fallback", data_status: "DEMO", model_status: "DEMO",
  atmospheric: { temperature_c: 25, humidity_pct: 60, pressure_hpa: 1000, wind_speed_ms: 2, cape_jkg: 0, cin_jkg: 0, precipitation_mm_h: 0 },
};
const risk = { forecast: "Demo only", confidence: 0.8, risk_level: "LOW", alerts: [], timestamp: prediction.timestamp, latitude: 12, longitude: 77, model_version: "demo-v1" };

describe("central prediction API client", () => {
  beforeEach(() => vi.stubGlobal("fetch", vi.fn()));

  it("joins backend prediction and risk responses and retains DEMO status", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => new Response(JSON.stringify(String(input).endsWith("/risk") ? risk : prediction), { status: 200 }));
    const result = await getPrediction(12, 77);
    expect(result.riskLevel).toBe("LOW");
    expect(result.riskProbability).toBe(20);
    expect(result.dataStatus).toBe("DEMO");
    expect(result.modelStatus).toBe("DEMO");
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("surfaces API failures without creating fallback predictions", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "unavailable" }), { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "unavailable" }), { status: 503 }));
    await expect(getPrediction(12, 77)).rejects.toThrow("unavailable");
  });
});
