import { useEffect, useState } from "react";
import type { Map as MapLibreMap } from "maplibre-gl";
import type { RiskLevel } from "../types/prediction";

// Display radius is illustrative only: M5 currently supplies one point score, not a spatial forecast grid.
const configuredRadius = Number(import.meta.env.VITE_RISK_FIELD_RADIUS_KM ?? "80");
const BASE_RADIUS_KM = Number.isFinite(configuredRadius) && configuredRadius > 0 ? configuredRadius : 80;

interface RiskLayerProps {
  map: MapLibreMap | null;
  latitude: number | null;
  longitude: number | null;
  riskLevel: RiskLevel | null;
  probability: number;
  opacity?: number;
}

const RISK_COLORS: Record<RiskLevel, string> = {
  LOW: "#3fb950",
  MODERATE: "#d7a11e",
  HIGH: "#e86a3d",
  SEVERE: "#d64545",
};

function circleCoordinates(lat: number, lon: number, radiusKm: number, steps = 96): number[][] {
  const result: number[][] = [];
  const earthRadius = 6371;
  const latRad = (lat * Math.PI) / 180;
  for (let i = 0; i <= steps; i += 1) {
    const angle = (i / steps) * Math.PI * 2;
    const dLat = (radiusKm / earthRadius) * Math.cos(angle);
    const dLon = (radiusKm / earthRadius) * Math.sin(angle) / Math.max(Math.cos(latRad), 0.15);
    result.push([lon + (dLon * 180) / Math.PI, lat + (dLat * 180) / Math.PI]);
  }
  return result;
}

function RiskLayer({ map, latitude, longitude, riskLevel, probability, opacity = 0.24 }: RiskLayerProps) {
  const [active, setActive] = useState(false);
  useEffect(() => {
    if (!map || latitude === null || longitude === null || !riskLevel) { setActive(false); return; }

    const sourceId = "strikecast-risk-field";
    const fillId = "strikecast-risk-fill";
    const lineId = "strikecast-risk-line";

    const probabilityFraction = Math.max(0, Math.min(1, probability / 100));
    const outer = BASE_RADIUS_KM * (0.65 + probabilityFraction * 0.35);
    const rings = [
      { radius: outer, level: riskLevel },
      { radius: outer * 0.68, level: riskLevel },
      { radius: outer * 0.38, level: riskLevel },
    ];

    const features = rings.map((ring, index) => ({
      type: "Feature" as const,
      properties: { risk: ring.level, ring: index },
      geometry: { type: "Polygon" as const, coordinates: [circleCoordinates(latitude, longitude, ring.radius)] },
    }));

    const data = { type: "FeatureCollection" as const, features };

    const draw = () => {
      if (!map.isStyleLoaded()) return false;
      if (map.getLayer(fillId)) map.removeLayer(fillId);
      if (map.getLayer(lineId)) map.removeLayer(lineId);
      if (map.getSource(sourceId)) map.removeSource(sourceId);
      map.addSource(sourceId, { type: "geojson", data });
      map.addLayer({ id: fillId, type: "fill", source: sourceId, paint: {
        "fill-color": RISK_COLORS[riskLevel],
        "fill-opacity": ["interpolate", ["linear"], ["get", "ring"], 0, opacity * 0.10, 1, opacity * 0.17, 2, opacity * 0.27],
      } });
      map.addLayer({ id: lineId, type: "line", source: sourceId, paint: {
        "line-color": RISK_COLORS[riskLevel],
        "line-width": ["interpolate", ["linear"], ["zoom"], 4, 0.7, 10, 1.6],
        "line-opacity": 0.55, "line-dasharray": [2, 2],
      } });
      setActive(true);
      return true;
    };
    const drawWhenIdle = () => {
      if (draw()) map.off("idle", drawWhenIdle);
    };
    if (!draw()) map.on("idle", drawWhenIdle);
    map.on("style.load", draw);

    return () => {
      map.off("style.load", draw);
      map.off("idle", drawWhenIdle);
      if (map.getLayer(fillId)) map.removeLayer(fillId);
      if (map.getLayer(lineId)) map.removeLayer(lineId);
      if (map.getSource(sourceId)) map.removeSource(sourceId);
      setActive(false);
    };
  }, [map, latitude, longitude, riskLevel, probability, opacity]);

  if (!active || latitude === null || longitude === null || !riskLevel) return null;
  return <span
    data-testid="risk-field-active"
    data-latitude={latitude}
    data-longitude={longitude}
    data-probability={probability}
    data-risk-level={riskLevel}
    hidden
  />;
}

export default RiskLayer;
