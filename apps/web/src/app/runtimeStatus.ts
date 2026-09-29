import type { MetadataResponse, PredictionResponse } from "../types/prediction";

export type RuntimeStatus = "LIVE" | "DEMO" | "OFFLINE" | "UNAVAILABLE";
export type ModelStatus = "TRAINED" | "CANDIDATE" | "UNTRAINED" | "DEMO" | "UNAVAILABLE";

export function getDataStatus(apiOnline: boolean, prediction: PredictionResponse | null): RuntimeStatus {
  if (!apiOnline) return "OFFLINE";
  if (!prediction) return "UNAVAILABLE";
  return prediction.dataStatus;
}

export function getModelStatus(metadata: MetadataResponse | null, prediction: PredictionResponse | null): ModelStatus {
  const status = (metadata?.model_status ?? prediction?.modelStatus ?? "").toLowerCase();
  if (status === "unavailable") return "UNAVAILABLE";
  if (status.includes("demo") || status.includes("mock")) return "DEMO";
  if (status.includes("production") || status === "trained" || status === "validated") return "TRAINED";
  if (status.includes("candidate") || status.includes("validated")) return "CANDIDATE";
  return "UNTRAINED";
}

export function getEvaluationStatus(metadata: MetadataResponse | null): "VALIDATED" | "NOT_AVAILABLE" {
  return metadata?.evaluation_status?.toLowerCase() === "validated" ? "VALIDATED" : "NOT_AVAILABLE";
}

export function getProviderStatus(configured: boolean, providerResponded: boolean, demo = false): RuntimeStatus {
  if (demo && providerResponded) return "DEMO";
  if (configured && providerResponded) return "LIVE";
  return "UNAVAILABLE";
}
