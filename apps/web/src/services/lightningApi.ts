import type { LightningResponse } from "../types/prediction";
import { requestApiJson } from "./apiClient";

export function getLightning(latitude: number, longitude: number): Promise<LightningResponse> {
  const query = `?latitude=${encodeURIComponent(latitude)}&longitude=${encodeURIComponent(longitude)}`;
  return requestApiJson<LightningResponse>(`/lightning${query}`);
}
