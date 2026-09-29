import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import type { Map as MapLibreMap } from "maplibre-gl";
import { Activity, Bell, Crosshair, Database, Layers3, LocateFixed, LogOut, MapPinned, RefreshCw, Search, ShieldCheck, Wind, Zap } from "lucide-react";
import LoginPage from "../components/Auth/LoginPage";
const AtmosphericScene = lazy(() => import("../components/Three/AtmosphericScene"));
const StrikeMap = lazy(() => import("../map/StrikeMap"));
const RiskLayer = lazy(() => import("../map/RiskLayer"));
const LightningLayer = lazy(() => import("../map/LightningLayer"));
const WeatherProductLayers = lazy(() => import("../products/WeatherProductLayers"));
const AnalyticProductOverlay = lazy(() => import("../products/AnalyticProductOverlay"));
import { checkApiHealth, getMetadata, getPrediction } from "../services/predictionApi";
import { reverseGeocode, searchLocation } from "../services/geocodingApi";
import type { GeocodingResult } from "../services/geocodingApi";
import type { MetadataResponse, PredictionResponse, RiskLevel } from "../types/prediction";
import { getDataStatus, getEvaluationStatus, getModelStatus } from "./runtimeStatus";

const DEFAULT_LOCATION = { latitude: 12.9716, longitude: 77.5946, name: "Bengaluru / India" };
const riskTone: Record<RiskLevel, string> = { LOW: "#49d28b", MODERATE: "#ffc329", HIGH: "#ff754f", SEVERE: "#ff4058" };
type Product = "BASE" | "SURFACE" | "SATELLITE" | "RADAR" | "ISOBAR" | "WIND" | "PRECIP" | "LIGHTNING" | "AI_RISK";
const products: { id: Product; label: string }[] = [
  { id: "BASE", label: "BASE MAP" }, { id: "SURFACE", label: "SURFACE" }, { id: "SATELLITE", label: "SATELLITE" },
  { id: "RADAR", label: "RADAR" }, { id: "ISOBAR", label: "ISOBAR" }, { id: "WIND", label: "WIND" },
  { id: "PRECIP", label: "PRECIP" }, { id: "LIGHTNING", label: "⚡ LIGHTNING" }, { id: "AI_RISK", label: "AI RISK" },
];

function formatTime(iso?: string | null) {
  if (!iso) return "--:--:--";
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [map, setMap] = useState<MapLibreMap | null>(null);
  const [location, setLocation] = useState(DEFAULT_LOCATION);
  const [placeName, setPlaceName] = useState(DEFAULT_LOCATION.name);
  const [prediction, setPrediction] = useState<PredictionResponse | null>(null);
  const [metadata, setMetadata] = useState<MetadataResponse | null>(null);
  const [apiOnline, setApiOnline] = useState(false);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<GeocodingResult[]>([]);
  const [showResults, setShowResults] = useState(false);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");
  const [product, setProduct] = useState<Product>("AI_RISK");
  const [riskOpacity, setRiskOpacity] = useState(0.28);
  const [productStatus, setProductStatus] = useState<"LIVE" | "DEMO" | "UNAVAILABLE" | "LOADING" | "ERROR">("UNAVAILABLE");
  const searchTimer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(searchTimer.current), []);

  const runPrediction = useCallback(async (lat: number, lon: number) => {
    setLoading(true); setError(""); setPrediction(null);
    try { const value = await getPrediction(lat, lon); setPrediction(value); setApiOnline(true); }
    catch (e) { setApiOnline(false); setError(e instanceof Error ? e.message : "M5 prediction service unavailable."); }
    finally { setLoading(false); }
  }, []);

  const selectLocation = useCallback(async (lat: number, lon: number, name?: string) => {
    map?.flyTo({ center: [lon, lat], zoom: Math.max(map.getZoom(), 7), duration: 900 });
    setLocation({ latitude: lat, longitude: lon, name: name ?? "Selected location" });
    if (name) { setPlaceName(name); setQuery(name); }
    else {
      try { const r = await reverseGeocode(lat, lon); const short = r?.displayName?.split(",").slice(0, 3).join(", ") ?? "Selected location"; setPlaceName(short); }
      catch { setPlaceName("Selected location"); }
    }
    await runPrediction(lat, lon);
  }, [map, runPrediction]);

  useEffect(() => {
    if (!authenticated) return;
    let alive = true;
    const boot = async () => {
      try { const [health, meta] = await Promise.all([checkApiHealth(), getMetadata()]); if (!alive) return; setApiOnline(health.status === "ok"); setMetadata(meta); }
      catch { if (alive) setApiOnline(false); }
    };
    void boot(); void runPrediction(DEFAULT_LOCATION.latitude, DEFAULT_LOCATION.longitude);
    const timer = window.setInterval(boot, 30000);
    return () => { alive = false; window.clearInterval(timer); };
  }, [authenticated, runPrediction]);

  useEffect(() => {
    if (!authenticated) return;
    const timer = window.setInterval(() => void runPrediction(location.latitude, location.longitude), 60000);
    return () => window.clearInterval(timer);
  }, [authenticated, location, runPrediction]);

  const handleSearch = useCallback(async () => {
    if (!query.trim()) return;
    window.clearTimeout(searchTimer.current);
    setSearching(true); setShowResults(true); setError("");
    searchTimer.current = window.setTimeout(async () => {
      try { setResults(await searchLocation(query.trim())); }
      catch { setResults([]); setError("Location search failed."); }
      finally { setSearching(false); }
    }, 300);
  }, [query]);

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => { if (e.key === "Enter") { e.preventDefault(); void handleSearch(); } if (e.key === "Escape") setShowResults(false); };
  const logout = () => setAuthenticated(false);
  const risk = prediction?.riskLevel ?? null;
  const riskLabel = risk ?? "UNAVAILABLE";
  const probability = prediction?.riskProbability ?? 0;
  const confidence = prediction?.confidence ?? 0;
  const tone = risk ? riskTone[risk] : "#9aa4b2";
  const atm = prediction?.atmospheric;
  const isLightning = product === "LIGHTNING";
  const isRisk = product === "AI_RISK";
  const dataStatus = getDataStatus(apiOnline, prediction);
  const modelStatus = getModelStatus(metadata, prediction);
  const evaluationStatus = getEvaluationStatus(metadata);
  const overlayProduct = useMemo(() => ["SURFACE", "ISOBAR", "WIND", "PRECIP"].includes(product) ? product as "SURFACE" | "ISOBAR" | "WIND" | "PRECIP" : "BASE", [product]);

  if (!authenticated) return <LoginPage onLogin={() => setAuthenticated(true)} />;

  return (
    <div className="command-center">
      <header className="command-topbar">
        <div className="brand-area">
          <div className="brand-bolt"><Zap size={20} fill="currentColor" /></div>
          <div><div className="brand-name">STRIKECAST</div><div className="brand-subtitle">AI LIGHTNING &amp; ATMOSPHERIC<br />INTELLIGENCE</div></div>
        </div>
        <div className="top-metrics">
          <div><span>SYSTEM</span><b className={apiOnline ? "ok" : "bad"}>{apiOnline ? "ONLINE" : "OFFLINE"}</b></div>
          <div><span>DATA</span><b className={dataStatus === "LIVE" ? "ok" : "bad"}>{dataStatus}</b></div>
          <div><span>MODEL</span><b>{modelStatus}</b></div>
          <div><span>LAST SYNC</span><b>{formatTime(prediction?.timestamp)}</b></div>
        </div>
          <div className="top-actions"><button title="Refresh" onClick={() => void runPrediction(location.latitude, location.longitude)}><RefreshCw size={14} className={loading ? "spin" : ""} /></button><div className="online-box"><ShieldCheck size={13} /> SYSTEM<br /><strong>{apiOnline ? "ONLINE" : "OFFLINE"}</strong></div><button title="Leave demo" onClick={logout}><LogOut size={14} /></button></div>
      </header>

      <main className="map-viewport">
        <Suspense fallback={<div className="map-loading" role="status">Loading map and visualization layers…</div>}>
        <StrikeMap onLocationSelect={(lat, lon) => void selectLocation(lat, lon)} onMapReady={setMap} />
        <WeatherProductLayers map={map} product={product === "SATELLITE" || product === "RADAR" ? product : "BASE"} onStatus={setProductStatus} />
        <AnalyticProductOverlay product={overlayProduct} atmospheric={atm} />
        <AtmosphericScene map={map} latitude={location.latitude} longitude={location.longitude} riskLevel={risk} probability={probability} />
        <RiskLayer map={map} latitude={location.latitude} longitude={location.longitude} riskLevel={risk} probability={probability} opacity={isRisk ? riskOpacity : 0} />
        <LightningLayer map={map} latitude={location.latitude} longitude={location.longitude} visible={isLightning} />
        </Suspense>

        <section className="hud search-panel">
          <div className="panel-kicker"><MapPinned size={12} /> LOCATION ACQUISITION <span>{placeName}</span></div>
          <div className="search-row"><Search size={15} /><input value={query} onChange={e => setQuery(e.target.value)} onKeyDown={handleKeyDown} onFocus={() => results.length && setShowResults(true)} placeholder="Search city, region, country" /><button onClick={() => void handleSearch()} disabled={searching}>{searching ? "…" : <Search size={16} />}</button></div>
          {showResults && results.length > 0 && <div className="search-results">{results.slice(0, 5).map((r, i) => <button key={`${r.latitude}-${r.longitude}-${i}`} onClick={() => { setShowResults(false); void selectLocation(r.latitude, r.longitude, r.displayName); }}><LocateFixed size={12} /><span>{r.displayName}</span></button>)}</div>}
          <div className="coords"><div><span>LAT</span><b>{location.latitude.toFixed(4)}°</b></div><div><span>LON</span><b>{location.longitude.toFixed(4)}°</b></div></div>
        </section>

        <section className="hud risk-panel">
          <div className="panel-kicker"><Activity size={12} /> CURRENT RISK <span>{prediction?.forecastHorizonMinutes ?? 60} MIN</span></div>
          <div className="risk-title" style={{ color: tone }}>{riskLabel}</div>
          <div className="risk-stat-grid"><div><span>{modelStatus === "DEMO" ? "DEMO SCORE (UNVALIDATED)" : "RAW PROBABILITY"}</span><strong>{probability.toFixed(1)}%</strong></div><div><span>DEMO CONFIDENCE (UNVALIDATED)</span><strong>{confidence.toFixed(1)}%</strong></div></div>
          <div className="model-lines"><span>MODEL <b>{prediction?.modelName ?? metadata?.model_name ?? "Unavailable"}</b></span><span>VERSION <b>{prediction?.modelVersion ?? metadata?.model_version ?? "—"}</b></span><span>EVALUATION <b>{evaluationStatus}</b></span><span>CALIBRATION <b>{prediction ? "NOT_VALIDATED" : "UNAVAILABLE"}</b></span><span>{modelStatus === "UNAVAILABLE" ? "LIVE FORECAST UNAVAILABLE" : `MODEL STATUS ${modelStatus}`}</span></div>
        </section>

        <section className="hud atmosphere-panel">
          <div className="panel-kicker"><Wind size={12} /> ATMOSPHERIC STATE <span>M1 / M2 TELEMETRY</span></div>
          <div className="telemetry-grid">
            <div><span>TEMPERATURE</span><b>{atm?.temperature_c != null ? `${atm.temperature_c.toFixed(1)} °C` : "N/A"}</b></div>
            <div><span>HUMIDITY</span><b>{atm?.humidity_pct != null ? `${atm.humidity_pct.toFixed(0)} %` : "N/A"}</b></div>
            <div><span>PRESSURE</span><b>{atm?.pressure_hpa != null ? `${atm.pressure_hpa.toFixed(0)} hPa` : "N/A"}</b></div>
            <div><span>WIND SPEED</span><b>{atm?.wind_speed_ms != null ? `${atm.wind_speed_ms.toFixed(1)} m/s` : "N/A"}</b></div>
            <div><span>WIND DIRECTION</span><b>{"N/A"}</b></div>
            <div><span>RAINFALL</span><b>{atm?.precipitation_mm_h != null ? `${atm.precipitation_mm_h.toFixed(1)} mm/h` : "N/A"}</b></div>
            <div><span>CAPE</span><b>{atm?.cape_jkg != null ? `${atm.cape_jkg.toFixed(0)} J/kg` : "N/A"}</b></div>
            <div><span>CIN</span><b>{atm?.cin_jkg != null ? `${atm.cin_jkg.toFixed(0)} J/kg` : "N/A"}</b></div>
          </div>
          <div className="data-source"><Database size={11} /> SOURCE <strong>{prediction?.dataSource ?? "UNAVAILABLE"}</strong></div>
        </section>

        <section className="hud alert-panel">
          <div className="panel-kicker"><Bell size={12} /> ALERT CENTER <i className="alert-dot" /></div>
          <div className="alert-main"><span>⚠</span><p>{prediction?.forecastText ?? "Awaiting M5 forecast response."}</p></div>
          <div className="alert-meta">{prediction?.alerts?.[0] ?? "Conditions are being evaluated from the current atmospheric state."}</div>
        </section>

        <section className="hud selected-panel">
          <div className="panel-kicker"><Crosshair size={12} /> SELECTED LOCATION</div>
          <strong>{placeName}</strong>
          <span>{location.latitude.toFixed(4)}°, {location.longitude.toFixed(4)}°</span>
        </section>

        <div className="product-dock">
          <div className="dock-label"><Layers3 size={12} /> ATMOSPHERIC PRODUCTS</div>
          <div className="dock-items">{products.map(item => <button key={item.id} className={`${product === item.id ? "active" : ""} ${item.id === "LIGHTNING" ? "lightning" : ""}`} onClick={() => setProduct(item.id)}>{item.label}</button>)}</div>
        </div>

        <div className="map-legend"><span><i className="dot low" />LOW</span><span><i className="dot moderate" />MODERATE</span><span><i className="dot high" />HIGH</span><span><i className="dot severe" />SEVERE</span></div>
        <div className="layer-badge">{isLightning ? "⚡ LIGHTNING OBSERVATIONS" : isRisk ? `${modelStatus === "DEMO" ? "DEMO POINT SCORE" : modelStatus === "TRAINED" ? "POINT RISK" : "RISK UNAVAILABLE"} · ILLUSTRATIVE RADIUS · ${riskLabel}` : `${products.find(p => p.id === product)?.label} · ${product === "SATELLITE" || product === "RADAR" ? productStatus : product === "SURFACE" && prediction ? prediction.dataStatus : "UNAVAILABLE"}`}</div>
        {error && <div className="map-error">{error}</div>}
      </main>
    </div>
  );
}

export default App;
