# StrikeCast Meteorological Product Layers

## Product switcher

M6 provides these selectable products:

- Base map
- Surface observation
- Satellite imagery
- Weather radar
- Isobar analysis
- Wind visualization
- Precipitation visualization
- Lightning observations
- StrikeCast AI Risk

## Data provenance

Satellite and radar overlays use configurable MapLibre raster tiles. The default educational setup uses RainViewer's public satellite tiles and Weather Maps API. The UI displays attribution.

Isobar, wind and precipitation views in this demo are explicitly point-derived analytic visualizations from the selected M5 atmospheric observation. They are not presented as full numerical weather model fields.

Lightning is separated from AI risk. The M5 `/lightning` adapter supports a live provider endpoint through environment variables and also has an explicit demo simulation mode for offline presentations. Demo strikes are labeled as simulation in the UI.

## Live lightning configuration

In root `.env` (loaded by `apps/api/strikecast_api/main.py`):

```env
LIGHTNING_MODE=live
LIGHTNING_FEED_URL=https://your-authorized-provider.example/geojson
LIGHTNING_FEED_BEARER=
```

The provider response may be a GeoJSON FeatureCollection or a simple array/object containing `latitude`/`longitude` (or `lat`/`lon`) and timestamp fields.
