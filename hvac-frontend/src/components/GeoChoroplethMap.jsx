import { useRef } from "react";
import { MapContainer, TileLayer, GeoJSON, ZoomControl } from "react-leaflet";
import "leaflet/dist/leaflet.css";

const NAVY = [30, 58, 95];
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

export default function GeoChoroplethMap({
  geoData,
  regions,
  maxCount,
  total,
  center,
  zoom,
  getKey,
  title,
  caption,
  isLoading,
  isError,
  children,
}) {
  const geoJsonKey = useRef(0);

  if (isLoading) return <LoadingSkeleton />;

  if (isError) {
    return (
      <div className="card h-full flex items-center justify-center p-6">
        <p className="text-ink-500 text-sm">Could not load geographic data.</p>
      </div>
    );
  }

  const countByKey = {};
  const cityByKey = {};
  const nameByKey = {};
  if (regions) {
    for (const r of regions) {
      countByKey[r.key] = r.count;
      cityByKey[r.key] = r.top_city;
      nameByKey[r.key] = r.name;
    }
  }

  function styleForFeature(feature) {
    const key = getKey(feature);
    const count = countByKey[key] ?? 0;
    const ratio = maxCount ? Math.max(0.1, count / maxCount) : 0.05;
    return {
      fillColor: `rgb(${NAVY[0]}, ${NAVY[1]}, ${NAVY[2]})`,
      fillOpacity: count > 0 ? ratio : 0.04,
      color: "#1E3A5F",
      weight: 1,
      opacity: 0.6,
    };
  }

  function attachTooltip(feature, layer) {
    const key = getKey(feature);
    const count = countByKey[key] ?? 0;
    const city = cityByKey[key] ?? null;
    const name = nameByKey[key] ?? feature.properties?.name ?? key;

    layer.bindTooltip(
      `<div style="font-family:Inter,system-ui;padding:2px 4px">
         <div style="font-weight:600;color:#0F172A;font-size:13px">${name}</div>
         <div style="color:#475569;font-size:12px">${count.toLocaleString()} complaints</div>
         ${city ? `<div style="color:#475569;font-size:11px;margin-top:2px">Top city: ${city}</div>` : ""}
       </div>`,
      { sticky: true, direction: "auto" }
    );

    layer.on({
      mouseover: (e) => e.target.setStyle({ weight: 2, color: "#15294A" }),
      mouseout: (e) => e.target.setStyle({ weight: 1, color: "#1E3A5F" }),
    });
  }

  geoJsonKey.current += 1;

  return (
    <div className="card h-full flex flex-col p-6">
      <div className="mb-4 flex-shrink-0">
        <h2 className="text-2xl font-bold text-ink-900 mb-1">{title}</h2>
        <p className="text-ink-500 text-sm">{caption}</p>
      </div>

      <div className="flex-1 overflow-hidden rounded-xl min-h-[400px]">
        <MapContainer
          center={center}
          zoom={zoom}
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
          {geoData && (
            <GeoJSON
              key={geoJsonKey.current}
              data={geoData}
              style={styleForFeature}
              onEachFeature={attachTooltip}
            />
          )}
          {children}
        </MapContainer>
      </div>

      <div className="mt-4 flex items-center justify-between flex-wrap gap-3 flex-shrink-0">
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
        {total != null && (
          <span className="text-ink-500 text-sm">
            Total: {total.toLocaleString()} complaints
          </span>
        )}
      </div>
    </div>
  );
}
