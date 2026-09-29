import type { AtmosphericData } from "../types/prediction";

type Product = "BASE" | "SURFACE" | "ISOBAR" | "WIND" | "PRECIP";

export default function AnalyticProductOverlay({ product, atmospheric }: { product: Product; atmospheric?: AtmosphericData }) {
  if (product === "BASE") return null;
  if (product !== "SURFACE") return <div className="product-overlay"><div className="product-tag">{product} · UNAVAILABLE · GRID PROVIDER NOT CONFIGURED</div></div>;
  if (!atmospheric) return <div className="product-overlay"><div className="product-tag">SURFACE · UNAVAILABLE</div></div>;
  return (
    <div className="product-overlay surface-product">
      <div className="product-tag">SURFACE POINT OBSERVATION · NOT A GRID</div>
      <div className="surface-values">
        <span>TEMP <b>{atmospheric.temperature_c.toFixed(1)}°C</b></span>
        <span>RH <b>{atmospheric.humidity_pct.toFixed(0)}%</b></span>
        <span>PRESS <b>{atmospheric.pressure_hpa.toFixed(0)} hPa</b></span>
      </div>
    </div>
  );
}
