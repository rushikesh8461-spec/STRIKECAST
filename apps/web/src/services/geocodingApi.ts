export interface GeocodingResult {
  latitude: number;
  longitude: number;
  displayName: string;
}

interface NominatimSearchResult {
  lat: string;
  lon: string;
  display_name: string;
}

interface NominatimReverseResult {
  lat: string;
  lon: string;
  display_name: string;
}

const NOMINATIM_SEARCH_URL =
  "https://nominatim.openstreetmap.org/search";

const NOMINATIM_REVERSE_URL =
  "https://nominatim.openstreetmap.org/reverse";

async function fetchProviderJson<T>(url: string): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch(url, { signal: controller.signal, redirect: "error", headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`Location provider failed: ${response.status}`);
    if (!response.headers.get("content-type")?.includes("application/json")) throw new Error("Location provider returned an unexpected content type");
    const text = await response.text();
    if (text.length > 1_000_000) throw new Error("Location provider response exceeded size limit");
    return JSON.parse(text) as T;
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function searchLocation(
  query: string,
): Promise<GeocodingResult[]> {
  const trimmedQuery = query.trim();

  if (!trimmedQuery) {
    return [];
  }

  const params = new URLSearchParams({
    q: trimmedQuery,
    format: "jsonv2",
    limit: "5",
    countrycodes: "in",
    addressdetails: "1",
    "accept-language": "en",
  });

  const data = await fetchProviderJson<NominatimSearchResult[]>(`${NOMINATIM_SEARCH_URL}?${params.toString()}`);

  return data
    .filter((result): result is NominatimSearchResult => Boolean(result && typeof result === "object"
      && typeof result.display_name === "string" && result.display_name.length <= 300))
    .map((result) => ({
      latitude: Number(result.lat),
      longitude: Number(result.lon),
      displayName: result.display_name,
    }))
    .filter(
      (result) =>
        Number.isFinite(result.latitude) &&
        Number.isFinite(result.longitude) && result.latitude >= -90 && result.latitude <= 90
        && result.longitude >= -180 && result.longitude <= 180,
    );
}

export async function reverseGeocode(
  latitude: number,
  longitude: number,
): Promise<GeocodingResult | null> {
  const params = new URLSearchParams({
    lat: String(latitude),
    lon: String(longitude),
    format: "jsonv2",
    zoom: "14",
    addressdetails: "1",
    "accept-language": "en",
  });

  const data = await fetchProviderJson<NominatimReverseResult>(`${NOMINATIM_REVERSE_URL}?${params.toString()}`);

  if (typeof data.display_name !== "string" || data.display_name.length > 300) {
    return null;
  }

  const parsedLatitude = Number(data.lat);
  const parsedLongitude = Number(data.lon);
  if (!Number.isFinite(parsedLatitude) || !Number.isFinite(parsedLongitude)
      || parsedLatitude < -90 || parsedLatitude > 90 || parsedLongitude < -180 || parsedLongitude > 180) return null;

  return {
    latitude: parsedLatitude,
    longitude: parsedLongitude,
    displayName: data.display_name,
  };
}
