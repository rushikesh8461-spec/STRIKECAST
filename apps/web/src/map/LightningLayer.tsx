import { useEffect, useState } from "react";
import type { Map as MapLibreMap } from "maplibre-gl";
import { getLightning } from "../services/lightningApi";
import type { LightningStrike } from "../types/prediction";

export default function LightningLayer({ map, latitude, longitude, visible }: { map: MapLibreMap | null; latitude: number | null; longitude: number | null; visible: boolean }) {
  const [strikes, setStrikes] = useState<LightningStrike[]>([]);
  const [mode, setMode] = useState<"live" | "demo" | "none">("none");

  useEffect(() => {
    if (!visible || latitude == null || longitude == null) { setStrikes([]); setMode("none"); return; }
    let active = true;
    const load = async () => {
      try { const response = await getLightning(latitude, longitude); if (active) { setStrikes(response.strikes); setMode(response.mode); } }
      catch { if (active) { setStrikes([]); setMode("none"); } }
    };
    void load();
    const timer = window.setInterval(load, 30000);
    return () => { active = false; window.clearInterval(timer); };
  }, [visible, latitude, longitude]);

  useEffect(() => {
    if (!map) return;
    const sourceId = "strikecast-lightning";
    const layerId = "strikecast-lightning-points";
    const glowId = "strikecast-lightning-glow";
    const cleanup = () => { if (map.getLayer(layerId)) map.removeLayer(layerId); if (map.getLayer(glowId)) map.removeLayer(glowId); if (map.getSource(sourceId)) map.removeSource(sourceId); };
    cleanup();
    if (!visible || !strikes.length) return;
    const data = { type: "FeatureCollection", features: strikes.map((s) => ({ type: "Feature", geometry: { type: "Point", coordinates: [s.longitude, s.latitude] }, properties: { age: s.age_minutes ?? 0, polarity: s.polarity ?? 0 } })) } as GeoJSON.FeatureCollection<GeoJSON.Point>;
    map.addSource(sourceId, { type: "geojson", data });
    map.addLayer({ id: glowId, type: "circle", source: sourceId, paint: { "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 8, 9, 14], "circle-color": "#f8d96b", "circle-opacity": 0.16, "circle-blur": 0.8 } });
    map.addLayer({ id: layerId, type: "circle", source: sourceId, paint: { "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 3, 9, 6], "circle-color": "#fff2a0", "circle-stroke-color": "#ffb84d", "circle-stroke-width": 1, "circle-opacity": 0.96 } });
    return cleanup;
  }, [map, strikes, visible]);

  if (!visible) return null;
  return <div className={`lightning-feed-badge ${mode}`}><span>⚡</span>{mode === "live" ? "LIVE LIGHTNING" : mode === "demo" ? "LIGHTNING SIMULATION" : "LIGHTNING FEED OFFLINE"}<b>{strikes.length}</b></div>;
}
