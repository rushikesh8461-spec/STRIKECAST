import { useEffect } from "react";
import type { ErrorEvent, Map as MapLibreMap } from "maplibre-gl";

type Product = "BASE" | "SATELLITE" | "RADAR";
export type ProviderStatus = "LIVE" | "DEMO" | "UNAVAILABLE" | "LOADING" | "ERROR";

const SATELLITE_TILES = import.meta.env.VITE_SATELLITE_TILES_URL ?? "";
const RADAR_API = import.meta.env.VITE_RADAR_API_URL ?? "";

export default function WeatherProductLayers({ map, product, onStatus }: {
  map: MapLibreMap | null;
  product: Product;
  onStatus?: (status: ProviderStatus) => void;
}) {
  useEffect(() => {
    if (!map) return;
    let cancelled = false;
    let timeout: number | undefined;
    const id = product === "SATELLITE" ? "strikecast-satellite" : "strikecast-radar";
    const remove = (sourceId: string) => {
      if (map.getLayer(sourceId)) map.removeLayer(sourceId);
      if (map.getSource(sourceId)) map.removeSource(sourceId);
    };
    remove("strikecast-satellite");
    remove("strikecast-radar");

    const onSourceData = (event: { sourceId?: string; sourceDataType?: string }) => {
      if (event.sourceId === id && event.sourceDataType === "content") onStatus?.("LIVE");
    };
    const onMapError = (_event: ErrorEvent) => {
      if (product === "SATELLITE" || product === "RADAR") onStatus?.("ERROR");
    };
    map.on("sourcedata", onSourceData);
    map.on("error", onMapError);

    const addRaster = (tiles: string[]) => {
      if (cancelled || map.getSource(id)) return;
      map.addSource(id, { type: "raster", tiles, tileSize: 256, attribution: "Weather imagery provider" });
      const before = map.getLayer("strikecast-risk-fill") ? "strikecast-risk-fill" : undefined;
      map.addLayer({ id, type: "raster", source: id, paint: { "raster-opacity": product === "RADAR" ? 0.72 : 0.78 } }, before);
    };

    if (product === "SATELLITE") {
      onStatus?.("UNAVAILABLE");
      if (SATELLITE_TILES) {
        try {
          const checked = new URL(SATELLITE_TILES.replaceAll("{z}", "0").replaceAll("{x}", "0").replaceAll("{y}", "0"));
          if (checked.protocol !== "https:" || checked.username || checked.password) throw new Error("Invalid satellite tile URL");
          onStatus?.("LOADING");
          addRaster([SATELLITE_TILES]);
        } catch { onStatus?.("ERROR"); }
      }
    } else if (product === "RADAR") {
      onStatus?.("UNAVAILABLE");
      if (RADAR_API) {
        onStatus?.("LOADING");
        const controller = new AbortController();
        timeout = window.setTimeout(() => controller.abort(), 8000);
        fetch(RADAR_API, { signal: controller.signal }).then(response => {
          if (!response.ok || !response.headers.get("content-type")?.includes("application/json")) {
            throw new Error("Radar provider response invalid");
          }
          return response.json();
        }).then((payload: { host?: string; radar?: { past?: { path: string }[] } }) => {
          if (cancelled) return;
          const frame = payload.radar?.past?.at(-1);
          if (!payload.host || !frame?.path || !frame.path.startsWith("/v2/radar/") || frame.path.includes("..")) {
            throw new Error("Radar provider metadata invalid");
          }
          const host = new URL(payload.host);
          if (host.protocol !== "https:" || !(host.hostname === "rainviewer.com" || host.hostname.endsWith(".rainviewer.com"))) {
            throw new Error("Radar provider host is not allowlisted");
          }
          addRaster([`${host.origin}${frame.path}/256/{z}/{x}/{y}/2/1_1.png`]);
        }).catch(() => { if (!cancelled) onStatus?.("ERROR"); })
          .finally(() => window.clearTimeout(timeout));
      }
    } else {
      onStatus?.("UNAVAILABLE");
    }

    return () => {
      cancelled = true;
      map.off("sourcedata", onSourceData);
      map.off("error", onMapError);
      window.clearTimeout(timeout);
    };
  }, [map, product, onStatus]);

  return null;
}
