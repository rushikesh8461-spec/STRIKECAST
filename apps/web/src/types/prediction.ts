export type RiskLevel = "LOW" | "MODERATE" | "HIGH" | "SEVERE";

export interface PredictionRequest {
  latitude: number;
  longitude: number;
  timestamp?: string;
  horizon_minutes?: number;
  grid?: unknown[][][] | null;
}

export interface AtmosphericData {
  temperature_c: number;
  humidity_pct: number;
  pressure_hpa: number;
  wind_speed_ms: number;
  cape_jkg: number;
  cin_jkg: number;
  precipitation_mm_h: number;
}

export interface PredictResponse {
  timestamp: string;
  forecast_horizon_minutes: number;
  latitude: number;
  longitude: number;
  grid_shape: number[] | null;
  prediction: number;
  probability: number;
  confidence: number;
  model_name: string;
  model_version: string;
  model_mode: string;
  data_source: string;
  data_status: "LIVE" | "DEMO" | "OFFLINE" | "UNAVAILABLE";
  model_status: "DEMO" | "DEMO_ONLY" | "CANDIDATE" | "UNTRAINED" | "TRAINED" | "UNAVAILABLE";
  atmospheric: AtmosphericData;
}

export interface RiskResponse {
  forecast: string;
  probability: number;
  calibrated_probability: number | null;
  confidence: number;
  calibration_status: string;
  risk_level: RiskLevel;
  alerts: string[];
  timestamp: string;
  latitude: number;
  longitude: number;
  model_version: string;
  risk_policy_version: string;
  forecast_horizon_minutes: number;
}

export interface PredictionResponse {
  latitude: number;
  longitude: number;
  riskProbability: number;
  riskLevel: RiskLevel;
  confidence: number;
  forecastText: string;
  alerts: string[];
  timestamp: string;
  modelVersion: string;
  modelName: string;
  modelMode: string;
  forecastHorizonMinutes: number;
  isDemo: boolean;
  dataSource: string;
  dataStatus: "LIVE" | "DEMO" | "OFFLINE" | "UNAVAILABLE";
  modelStatus: "DEMO" | "DEMO_ONLY" | "CANDIDATE" | "UNTRAINED" | "TRAINED" | "UNAVAILABLE";
  atmospheric: AtmosphericData;
}

export interface HealthResponse {
  status: string;
  model_mode?: string;
}

export interface MetadataResponse {
  service?: string;
  version?: string;
  model_name?: string;
  model_version?: string;
  model_mode?: string;
  model_status?: "candidate_demo_only" | string;
  evaluation_status?: "not_available" | "validated" | string;
  risk_threshold_status?: "provisional_unvalidated" | string;
  pipeline?: string[];
  risk_levels?: RiskLevel[];
}

export interface LightningStrike {
  latitude: number;
  longitude: number;
  timestamp: string;
  age_minutes?: number;
  polarity?: number;
  intensity?: number | null;
  source?: string | null;
  quality?: number | null;
}

export interface LightningResponse {
  mode: "live" | "demo" | "none";
  source_mode: "REAL" | "DEMO" | "UNAVAILABLE";
  source: string;
  updated_at: string;
  strikes: LightningStrike[];
}
