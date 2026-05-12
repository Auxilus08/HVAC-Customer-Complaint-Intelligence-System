import { useRef, useEffect } from "react";
import { MapContainer, TileLayer, GeoJSON, ZoomControl, useMap } from "react-leaflet";
import L from "leaflet";
import { useRegionHeatmap } from "../hooks/useAnalytics";
import { useComplaintLocations } from "../hooks/useComplaints";
import boroughGeo from "../data/nyc_boroughs.json";
import "leaflet/dist/leaflet.css";

const SENTIMENT_COLORS = {
  CRITICAL: "#DC2626",
  HIGH:     "#F59E0B",
  NORMAL:   "#94A3B8",
  POSITIVE: "#16A34A",
};

function DotsLayer({ points }) {
  const map = useMap();
  useEffect(() => {
    if (!points?.length) return;
    const renderer = L.canvas({ padding: 0.5 });
    const layer = L.layerGroup();
    for (const p of points) {
      const color = SENTIMENT_COLORS[p.sentiment] ?? "#CBD5E1";
      const marker = L.circleMarker([p.lat, p.lng], {
        renderer,
        radius: 3,
        color,
        weight: 0,
        fillColor: color,
        fillOpacity: 0.65,
      });
      const tooltipText = p.cluster_label
        ? `<b>${p.cluster_label}</b><br>${p.region}`
        : p.region;
      marker.bindTooltip(tooltipText, { sticky: true });
      marker.addTo(layer);
    }
    layer.addTo(map);
    return () => { layer.remove(); };
  }, [map, points]);
  return null;
}

const NAVY = [30, 58, 95]; // #1E3A5F
const LEGEND_STEPS = [0.1, 0.25, 0.45, 0.6, 0.8, 1.0];

function LoadingSkeleton() {
  return (
    <div className="card h-full flex flex-col p-6 animate-pulse">
      <div className="h-7 w-64 bg-ink-100 rounded mb-2" />
      <div className="h-4 w-96 bg-ink-100 rounded mb-6" />
      <div className="flex-1 bg-ink-100 rounded-xl min-h-[400px]" />
    </div>
  );
}

export default function BoroughMap() {
  const { data, isLoading, isError } = useRegionHeatmap();
  const locationsQ = useComplaintLocations();
  const geoJsonKey = useRef(0);

  if (isLoading) return <LoadingSkeleton />;

  if (isError) {
    return (
      <div className="card h-full flex items-center justify-center p-6">
        <p className="text-ink-500 text-sm">Couldn&apos;t load region data.</p>
      </div>
    );
  }

  const themes = data?.themes ?? [];
  const matrix = data?.matrix ?? [];
  const regions = data?.regions ?? [];

  // Uppercase region names for case-insensitive matching against GeoJSON
  const regionsUpper = regions.map((r) => r.toUpperCase());

  // Per-borough totals: sum across all theme rows for column j
  const totals = regionsUpper.map((_, j) =>
    matrix.reduce((s, row) => s + (row[j] ?? 0), 0)
  );

  // Dominant theme per borough: argmax over column j
  const topThemeIndex = regionsUpper.map((_, j) => {
    let best = 0;
    for (let i = 1; i < matrix.length; i++) {
      if ((matrix[i]?.[j] ?? 0) > (matrix[best]?.[j] ?? 0)) best = i;
    }
    return best;
  });

  const max = Math.max(...totals, 1);

  function styleForFeature(feature) {
    const name = (feature.properties.name || feature.properties.boro_name || "").trim();
    const idx = regionsUpper.indexOf(name.toUpperCase());
    const count = idx >= 0 ? totals[idx] : 0;
    const ratio = max ? Math.min(1, Math.max(0.1, count / max)) : 0;
    return {
      fillColor: `rgb(${NAVY[0]}, ${NAVY[1]}, ${NAVY[2]})`,
      fillOpacity: themes.length === 0 ? 0.08 : ratio,
      color: "#1E3A5F",
      weight: 2,
      opacity: 0.8,
    };
  }

  function attachTooltip(feature, layer) {
    const name = (feature.properties.name || feature.properties.boro_name || "").trim();
    const idx = regionsUpper.indexOf(name.toUpperCase());
    const count = idx >= 0 ? totals[idx] : 0;
    const topTheme = idx >= 0 ? themes[topThemeIndex[idx]] : null;

    layer.bindTooltip(
      `<div style="font-family:Inter,system-ui;padding:2px 4px">
         <div style="font-weight:600;color:#0F172A;font-size:13px">${name}</div>
         <div style="color:#475569;font-size:12px">${count.toLocaleString()} complaints</div>
         ${topTheme ? `<div style="color:#475569;font-size:11px;margin-top:2px">Top: ${topTheme.label}</div>` : ""}
       </div>`,
      { sticky: true, direction: "auto" }
    );

    layer.on({
      mouseover: (e) => e.target.setStyle({ weight: 3, color: "#15294A" }),
      mouseout: (e) => e.target.setStyle({ weight: 2, color: "#1E3A5F" }),
    });
  }

  // Increment key to force GeoJSON re-render when data loads
  geoJsonKey.current += 1;

  return (
    <div className="card h-full flex flex-col p-6">
      <div className="mb-4 flex-shrink-0">
        <h2 className="text-2xl font-bold text-ink-900 mb-1">Complaints Across NYC</h2>
        <p className="text-ink-500 text-sm">
          Each dot is a single complaint, placed approximately inside its reported borough. Color shows sentiment severity.
        </p>
      </div>

      <div className="flex-1 overflow-hidden rounded-xl min-h-[400px]">
        <MapContainer
          center={[40.7128, -74.006]}
          zoom={10}
          scrollWheelZoom={true}
          zoomControl={false}
          preferCanvas={true}
          style={{ height: "100%", width: "100%", borderRadius: 12 }}
          attributionControl={true}
        >
          <ZoomControl position="topright" />
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          />
          <GeoJSON
            key={geoJsonKey.current}
            data={boroughGeo}
            style={styleForFeature}
            onEachFeature={attachTooltip}
          />
          {locationsQ.data && (
            <DotsLayer points={locationsQ.data.points || []} />
          )}
        </MapContainer>
      </div>

      {themes.length === 0 && (
        <p className="text-ink-400 text-sm text-center mt-3 flex-shrink-0">No clustered data yet — map shown without shading.</p>
      )}

      <div className="mt-4 flex items-center justify-between flex-wrap gap-3 flex-shrink-0">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2 text-xs text-ink-500">
            <span>Fewer</span>
            {LEGEND_STEPS.map((alpha) => (
              <span
                key={alpha}
                className="inline-block w-5 h-5 rounded"
                style={{ backgroundColor: `rgba(${NAVY[0]}, ${NAVY[1]}, ${NAVY[2]}, ${alpha})` }}
              />
            ))}
            <span>More</span>
          </div>
          <div className="flex items-center gap-3 text-xs text-ink-500">
            <span>Sentiment:</span>
            {[
              { color: "#DC2626", label: "Critical" },
              { color: "#F59E0B", label: "High" },
              { color: "#94A3B8", label: "Normal" },
              { color: "#16A34A", label: "Positive" },
            ].map(({ color, label }) => (
              <span key={label} className="flex items-center gap-1">
                <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
                {label}
              </span>
            ))}
          </div>
        </div>
        <span className="text-ink-500 text-sm">
          Total: {totals.reduce((s, v) => s + v, 0).toLocaleString()} NYC complaints
        </span>
      </div>
    </div>
  );
}
