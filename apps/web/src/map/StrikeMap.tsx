import { useEffect, useRef } from "react";
import * as maplibregl from "maplibre-gl";
import type { MapMouseEvent } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";


interface StrikeMapProps {
  onLocationSelect?: (latitude: number, longitude: number) => void;
  onMapReady?: (map: maplibregl.Map) => void;
}

const fallbackStyle = {
  version: 8 as const,
  sources: {
    osm: {
      type: "raster" as const,
      tiles: [trustedTileUrl(import.meta.env.VITE_MAP_TILES_URL)],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [
    { id: "osm", type: "raster" as const, source: "osm" },
  ],
};

function trustedStyleUrl(candidate: string | undefined): string | undefined {
  if (!candidate) return undefined;
  try {
    const parsed = new URL(candidate);
    return parsed.protocol === "https:" && !parsed.username && !parsed.password ? candidate : undefined;
  } catch { return undefined; }
}

function trustedTileUrl(candidate: string | undefined): string {
  const fallback = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
  if (!candidate) return fallback;
  try {
    const parsed = new URL(candidate.replaceAll("{z}", "0").replaceAll("{x}", "0").replaceAll("{y}", "0"));
    return parsed.protocol === "https:" && !parsed.username && !parsed.password ? candidate : fallback;
  } catch { return fallback; }
}

function StrikeMap({ onLocationSelect, onMapReady }: StrikeMapProps) {
  const container = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markerRef = useRef<maplibregl.Marker | null>(null);
  const selectRef = useRef(onLocationSelect);
  const readyRef = useRef(onMapReady);

  useEffect(() => { selectRef.current = onLocationSelect; }, [onLocationSelect]);
  useEffect(() => { readyRef.current = onMapReady; }, [onMapReady]);

  useEffect(() => {
    if (!container.current || mapRef.current) return;

    const styleUrl = trustedStyleUrl(import.meta.env.VITE_MAP_STYLE_URL);
    const map = new maplibregl.Map({
      container: container.current,
      style: styleUrl || fallbackStyle,
      center: [78.9629, 22.5937],
      zoom: 4.5,
      minZoom: 3,
      maxZoom: 14,
      attributionControl: false,
    });

    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "top-right");
    map.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: "metric" }), "bottom-right");

    const resizeObserver = new ResizeObserver(() => map.resize());
    resizeObserver.observe(container.current);

    map.on("click", (event: MapMouseEvent) => {
      const { lng, lat } = event.lngLat;
      markerRef.current?.remove();
      const el = document.createElement("div");
      el.className = "forecast-pin";
      el.innerHTML = '<span class="forecast-pin-core"></span><span class="forecast-pin-ring"></span>';
      markerRef.current = new maplibregl.Marker({ element: el, anchor: "center" })
        .setLngLat([lng, lat])
        .addTo(map);
      selectRef.current?.(lat, lng);
    });

    map.on("load", () => { map.resize(); readyRef.current?.(map); });

    return () => {
      resizeObserver.disconnect();
      markerRef.current?.remove();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  return <div ref={container} className="strike-map-canvas" />;
}

export default StrikeMap;
