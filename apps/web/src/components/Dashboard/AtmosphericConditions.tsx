import type { PredictionResponse } from "../../types/prediction";
function AtmosphericConditions({prediction}:{prediction:PredictionResponse|null}){
 if(!prediction) return <div className="card atmospheric-card"><p className="card-label">ATMOSPHERIC CONDITIONS</p><div className="atmospheric-unavailable"><strong>Select a location</strong><p>Live atmospheric observations will appear here.</p></div></div>;
 const a=prediction.atmospheric;
 const rows=[['Temperature',`${a.temperature_c.toFixed(1)} °C`],['Humidity',`${a.humidity_pct.toFixed(0)} %`],['Pressure',`${a.pressure_hpa.toFixed(0)} hPa`],['Wind',`${a.wind_speed_ms.toFixed(1)} m/s`],['CAPE',`${a.cape_jkg.toFixed(0)} J/kg`],['CIN',`${a.cin_jkg.toFixed(0)} J/kg`],['Precipitation',`${a.precipitation_mm_h.toFixed(1)} mm/h`]];
 return <div className="card atmospheric-card"><p className="card-label">ATMOSPHERIC CONDITIONS</p><div className="atmospheric-grid">{rows.map(([k,v])=><div className="atmospheric-row" key={k}><span>{k}</span><strong>{v}</strong></div>)}</div><p className="atmospheric-source">Source: {prediction.dataSource}</p></div>;
}
export default AtmosphericConditions;
