import { describe, expect, it } from "vitest";
import { getDataStatus, getEvaluationStatus, getModelStatus, getProviderStatus } from "./runtimeStatus";
import type { PredictionResponse } from "../types/prediction";

const demoPrediction = { dataStatus: "DEMO", modelStatus: "DEMO" } as unknown as PredictionResponse;

describe("truthful runtime labels", () => {
  it("reports API-offline separately from missing prediction data", () => {
    expect(getDataStatus(false, demoPrediction)).toBe("OFFLINE");
    expect(getDataStatus(true, null)).toBe("UNAVAILABLE");
  });

  it("uses the API data state without upgrading demo data to live", () => {
    expect(getDataStatus(true, demoPrediction)).toBe("DEMO");
    expect(getDataStatus(true, { dataStatus: "LIVE" } as unknown as PredictionResponse)).toBe("LIVE");
  });

  it("maps missing, candidate, demo and validated model metadata", () => {
    expect(getModelStatus(null, null)).toBe("UNTRAINED");
    expect(getModelStatus({ model_status: "candidate" }, null)).toBe("CANDIDATE");
    expect(getModelStatus({ model_status: "candidate_demo_only" }, null)).toBe("DEMO");
    expect(getModelStatus({ model_status: "production" }, null)).toBe("TRAINED");
    expect(getModelStatus({ model_status: "unavailable" }, null)).toBe("UNAVAILABLE");
  });

  it("does not infer evaluation validity from model status", () => {
    expect(getEvaluationStatus({ model_status: "production" })).toBe("NOT_AVAILABLE");
    expect(getEvaluationStatus({ evaluation_status: "validated" })).toBe("VALIDATED");
  });

  it("keeps unconfigured map products unavailable and reports observed providers", () => {
    expect(getProviderStatus(false, false)).toBe("UNAVAILABLE");
    expect(getProviderStatus(true, false)).toBe("UNAVAILABLE");
    expect(getProviderStatus(true, true)).toBe("LIVE");
    expect(getProviderStatus(true, true, true)).toBe("DEMO");
  });
});
