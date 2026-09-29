import type { HealthResponse, MetadataResponse, PredictionRequest, PredictionResponse, PredictResponse, RiskResponse } from "../types/prediction";
import { getApiBaseUrl, requestApiJson } from "./apiClient";

function buildRequest(latitude: number, longitude: number): PredictionRequest {
  return { latitude, longitude, horizon_minutes: 60, grid: null };
}

export async function getPrediction(latitude: number, longitude: number): Promise<PredictionResponse> {
  const request = buildRequest(latitude, longitude);
  const [predict, risk] = await Promise.all([
    requestApiJson<PredictResponse>("/predict", { method: "POST", body: JSON.stringify(request) }),
    requestApiJson<RiskResponse>("/risk", { method: "POST", body: JSON.stringify(request) }),
  ]);
  return {
    latitude: risk.latitude,
    longitude: risk.longitude,
    riskProbability: predict.probability * 100,
    riskLevel: risk.risk_level,
    confidence: predict.confidence * 100,
    forecastText: risk.forecast,
    alerts: risk.alerts,
    timestamp: risk.timestamp,
    modelVersion: risk.model_version,
    modelName: predict.model_name,
    modelMode: predict.model_mode,
    modelStatus: predict.model_status,
    dataSource: predict.data_source,
    dataStatus: predict.data_status,
    atmospheric: predict.atmospheric,
    forecastHorizonMinutes: predict.forecast_horizon_minutes,
    isDemo: /demo|mock/i.test(`${predict.model_mode} ${predict.model_name}`),
  };
}

export function checkApiHealth(): Promise<HealthResponse> { return requestApiJson("/health"); }
export function getMetadata(): Promise<MetadataResponse> { return requestApiJson("/metadata"); }
export { getApiBaseUrl };
