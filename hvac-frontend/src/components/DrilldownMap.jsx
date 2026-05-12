import { useEffect, useRef, useState } from "react";
import { MapContainer, TileLayer, ZoomControl, useMap, useMapEvent } from "react-leaflet";
import L from "leaflet";
import { useGeo, useRegionHeatmap, useCities } from "../hooks/useAnalytics";
import { useComplaintLocations } from "../hooks/useComplaints";
import worldGeoRaw from "../data/world_countries.json";
import usaGeoRaw from "../data/us_states.json";
import indiaGeoRaw from "../data/india_states.json";
import boroughGeo from "../data/nyc_boroughs.json";
import "leaflet/dist/leaflet.css";

const NAVY = [30, 58, 95];
const LEGEND_STEPS = [0.1, 0.25, 0.45, 0.6, 0.8, 1.0];

// NYC bounding box for layer gating
const NYC_BBOX = { minLat: 40.5, maxLat: 40.9, minLng: -74.3, maxLng: -73.6 };

// Full state name → 2-letter postal code — needed to match PublicaMundi us_states.json
const STATE_NAME_TO_CODE = {
  "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
  "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
  "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI",
  "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
  "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
  "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
  "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
  "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
  "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
  "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI",
  "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX",
  "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
  "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY", "Puerto Rico": "PR",
};

const SENTIMENT_COLORS = {
  CRITICAL: "#DC2626",
  HIGH:     "#F59E0B",
  NORMAL:   "#94A3B8",
  POSITIVE: "#16A34A",
};

function zoomLabel(z) {
  if (z >= 9) return { title: "Neighborhood detail", caption: "5,000 individual complaints across NYC's 5 boroughs" };
  if (z >= 7) return { title: "City detail", caption: "Hover any dot for city-level counts" };
  if (z >= 4) return { title: "Country drill-down", caption: "Zoom in to see state and city detail" };
  return { title: "Global view", caption: "Carrier complaint volume across 40 countries" };
}

function buildWorldLayer(worldData) {
  const countByIso = {};
  const nameByIso = {};
  const cityByIso = {};
  let max = 0;
  if (worldData?.regions) {
    for (const r of worldData.regions) {
      countByIso[r.key] = r.count;
      nameByIso[r.key] = r.name;
      cityByIso[r.key] = r.top_city;
      if (r.count > max) max = r.count;
    }
  }

  return L.geoJSON(worldGeoRaw, {
    style(feature) {
      // Natural Earth has a few features where ISO_A3 is -99 — fall back to name
      const iso = feature.properties?.ISO_A3;
      const key = iso && iso !== "-99" ? iso : null;
      const count = key ? (countByIso[key] ?? 0) : 0;
      const ratio = max > 0 && count > 0 ? Math.max(0.1, count / max) : 0.04;
      return {
        fillColor: `rgb(${NAVY[0]},${NAVY[1]},${NAVY[2]})`,
        fillOpacity: count > 0 ? ratio : 0.04,
        color: "#1E3A5F",
        weight: 1,
        opacity: 0.6,
      };
    },
    onEachFeature(feature, layer) {
      const iso = feature.properties?.ISO_A3;
      const key = iso && iso !== "-99" ? iso : null;
      const count = key ? (countByIso[key] ?? 0) : 0;
      const name = key ? (nameByIso[key] ?? feature.properties?.name ?? key) : (feature.properties?.name ?? "");
      const city = key ? (cityByIso[key] ?? null) : null;
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
        mouseout:  (e) => e.target.setStyle({ weight: 1, color: "#1E3A5F" }),
      });
    },
  });
}

function buildUsaLayer(usaData) {
  const countByCode = {};
  const nameByCode = {};
  const cityByCode = {};
  let max = 0;
  if (usaData?.regions) {
    for (const r of usaData.regions) {
      countByCode[r.key] = r.count;
      nameByCode[r.key] = r.name;
      cityByCode[r.key] = r.top_city;
      if (r.count > max) max = r.count;
    }
  }

  return L.geoJSON(usaGeoRaw, {
    style(feature) {
      const stateName = feature.properties?.name ?? "";
      const code = STATE_NAME_TO_CODE[stateName] ?? stateName;
      const count = countByCode[code] ?? 0;
      const ratio = max > 0 && count > 0 ? Math.max(0.1, count / max) : 0.04;
      return {
        fillColor: `rgb(${NAVY[0]},${NAVY[1]},${NAVY[2]})`,
        fillOpacity: count > 0 ? ratio : 0.04,
        color: "#1E3A5F",
        weight: 1,
        opacity: 0.6,
      };
    },
    onEachFeature(feature, layer) {
      const stateName = feature.properties?.name ?? "";
      const code = STATE_NAME_TO_CODE[stateName] ?? stateName;
      const count = countByCode[code] ?? 0;
      const city = cityByCode[code] ?? null;
      layer.bindTooltip(
        `<div style="font-family:Inter,system-ui;padding:2px 4px">
           <div style="font-weight:600;color:#0F172A;font-size:13px">${stateName}</div>
           <div style="color:#475569;font-size:12px">${count.toLocaleString()} complaints</div>
           ${city ? `<div style="color:#475569;font-size:11px;margin-top:2px">Top city: ${city}</div>` : ""}
         </div>`,
        { sticky: true, direction: "auto" }
      );
      layer.on({
        mouseover: (e) => e.target.setStyle({ weight: 2, color: "#15294A" }),
        mouseout:  (e) => e.target.setStyle({ weight: 1, color: "#1E3A5F" }),
      });
    },
  });
}

function buildIndiaLayer(indiaData) {
  const countByName = {};
  const cityByName = {};
  let max = 0;
  if (indiaData?.regions) {
    for (const r of indiaData.regions) {
      countByName[r.name] = r.count;
      cityByName[r.name] = r.top_city;
      if (r.count > max) max = r.count;
    }
  }

  return L.geoJSON(indiaGeoRaw, {
    style(feature) {
      const name = feature.properties?.name ?? "";
      const count = countByName[name] ?? 0;
      const ratio = max > 0 && count > 0 ? Math.max(0.1, count / max) : 0.04;
      return {
        fillColor: `rgb(${NAVY[0]},${NAVY[1]},${NAVY[2]})`,
        fillOpacity: count > 0 ? ratio : 0.04,
        color: "#1E3A5F",
        weight: 1,
        opacity: 0.6,
      };
    },
    onEachFeature(feature, layer) {
      const name = feature.properties?.name ?? "";
      const count = countByName[name] ?? 0;
      const city = cityByName[name] ?? null;
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
        mouseout:  (e) => e.target.setStyle({ weight: 1, color: "#1E3A5F" }),
      });
    },
  });
}

function buildCityLayer(citiesData) {
  const group = L.layerGroup();
  if (!citiesData?.cities) return group;
  const maxCount = citiesData.max_count || 1;
  for (const c of citiesData.cities) {
    const radius = Math.max(4, Math.sqrt(c.count) / 5);
    const marker = L.circleMarker([c.lat, c.lng], {
      radius,
      fillColor: "#1E3A5F",
      fillOpacity: 0.7,
      color: "#0F172A",
      weight: 1,
    });
    marker.bindTooltip(
      `<div style="font-family:Inter,system-ui;padding:2px 4px">
         <div style="font-weight:600;color:#0F172A;font-size:13px">${c.name}</div>
         <div style="color:#475569;font-size:12px">${c.count.toLocaleString()} complaints</div>
         <div style="color:#475569;font-size:11px;margin-top:2px">${c.country}</div>
       </div>`,
      { sticky: true, direction: "auto" }
    );
    marker.addTo(group);
  }
  return group;
}

function buildBoroughLayer(regionData) {
  const themes = regionData?.themes ?? [];
  const matrix = regionData?.matrix ?? [];
  const regions = regionData?.regions ?? [];
  const regionsUpper = regions.map((r) => r.toUpperCase());

  const totals = regionsUpper.map((_, j) =>
    matrix.reduce((s, row) => s + (row[j] ?? 0), 0)
  );
  const topThemeIndex = regionsUpper.map((_, j) => {
    let best = 0;
    for (let i = 1; i < matrix.length; i++) {
      if ((matrix[i]?.[j] ?? 0) > (matrix[best]?.[j] ?? 0)) best = i;
    }
    return best;
  });
  const max = Math.max(...totals, 1);

  return L.geoJSON(boroughGeo, {
    style(feature) {
      const name = (feature.properties.name || feature.properties.boro_name || "").trim();
      const idx = regionsUpper.indexOf(name.toUpperCase());
      const count = idx >= 0 ? totals[idx] : 0;
      const ratio = Math.min(1, Math.max(0.1, count / max));
      return {
        fillColor: `rgb(${NAVY[0]},${NAVY[1]},${NAVY[2]})`,
        fillOpacity: themes.length === 0 ? 0.08 : ratio,
        color: "#1E3A5F",
        weight: 2,
        opacity: 0.8,
      };
    },
    onEachFeature(feature, layer) {
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
        mouseout:  (e) => e.target.setStyle({ weight: 2, color: "#1E3A5F" }),
      });
    },
  });
}

function buildDotsLayer(points) {
  const group = L.layerGroup();
  if (!points?.length) return group;
  const renderer = L.canvas({ padding: 0.5 });
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
    const tip = p.cluster_label ? `<b>${p.cluster_label}</b><br>${p.region}` : p.region;
    marker.bindTooltip(tip, { sticky: true });
    marker.addTo(group);
  }
  return group;
}

// ─── ZoomDrivenLayers — manages layer add/remove in response to zoom ──────────
function ZoomDrivenLayers({ worldData, usaData, indiaData, citiesData, regionData, locationsData, onZoomChange }) {
  const map = useMap();
  // Store layer refs so they survive re-renders without being recreated
  const layersRef = useRef(null);

  // Rebuild layers only when data changes
  useEffect(() => {
    // Dispose previous layers
    if (layersRef.current) {
      const prev = layersRef.current;
      [prev.world, prev.usa, prev.india, prev.cities, prev.boroughs, prev.dots].forEach((l) => {
        if (l && map.hasLayer(l)) map.removeLayer(l);
      });
    }

    const worldLayer   = buildWorldLayer(worldData);
    const usaLayer     = buildUsaLayer(usaData);
    const indiaLayer   = buildIndiaLayer(indiaData);
    const cityLayer    = buildCityLayer(citiesData);
    const boroughLayer = buildBoroughLayer(regionData);
    const dotsLayer    = buildDotsLayer(locationsData?.points ?? []);

    layersRef.current = { world: worldLayer, usa: usaLayer, india: indiaLayer, cities: cityLayer, boroughs: boroughLayer, dots: dotsLayer };

    function updateLayers() {
      const z = map.getZoom();
      onZoomChange(z);

      const { world, usa, india, cities, boroughs, dots } = layersRef.current;

      // World choropleth: visible at zoom ≤ 4
      if (z <= 4) {
        if (!map.hasLayer(world)) map.addLayer(world);
      } else {
        if (map.hasLayer(world)) map.removeLayer(world);
      }

      // State choropleths + city dots: visible at 4 ≤ z ≤ 8
      // (Removed at z ≥ 9 so NY-state polygon doesn't drown the NYC borough view.)
      if (z >= 4 && z <= 8) {
        if (!map.hasLayer(usa))    map.addLayer(usa);
        if (!map.hasLayer(india))  map.addLayer(india);
        if (!map.hasLayer(cities)) map.addLayer(cities);
      } else {
        if (map.hasLayer(usa))    map.removeLayer(usa);
        if (map.hasLayer(india))  map.removeLayer(india);
        if (map.hasLayer(cities)) map.removeLayer(cities);
      }

      // NYC borough polygons + complaint dots: zoom ≥ 9
      if (z >= 9) {
        if (!map.hasLayer(boroughs)) map.addLayer(boroughs);
        if (!map.hasLayer(dots))     map.addLayer(dots);
      } else {
        if (map.hasLayer(boroughs)) map.removeLayer(boroughs);
        if (map.hasLayer(dots))     map.removeLayer(dots);
      }
    }

    updateLayers();
    map.on("zoomend", updateLayers);

    return () => {
      map.off("zoomend", updateLayers);
      const { world, usa, india, cities, boroughs, dots } = layersRef.current;
      [world, usa, india, cities, boroughs, dots].forEach((l) => {
        if (l && map.hasLayer(l)) map.removeLayer(l);
      });
    };
  }, [map, worldData, usaData, indiaData, citiesData, regionData, locationsData]); // eslint-disable-line react-hooks/exhaustive-deps

  return null;
}

// ─── DrilldownMap — the exported page component ────────────────────────────
export default function DrilldownMap() {
  const [zoom, setZoom] = useState(2);
  const worldQ   = useGeo("world");
  const usaQ     = useGeo("usa");
  const indiaQ   = useGeo("india");
  const citiesQ  = useCities();
  const regionQ  = useRegionHeatmap();
  const locationsQ = useComplaintLocations();

  const { title, caption } = zoomLabel(zoom);

  const isLoading = worldQ.isLoading || usaQ.isLoading || indiaQ.isLoading || citiesQ.isLoading;

  return (
    <div className="h-full flex flex-col">
      {/* Header bar */}
      <div className="px-6 pt-4 pb-3 flex-shrink-0">
        <h2 className="text-xl font-bold text-ink-900 leading-tight">{title}</h2>
        <p className="text-ink-500 text-sm mt-0.5">{caption}</p>
      </div>

      {/* Map */}
      <div className="flex-1 min-h-0 px-6 pb-4 relative">
        {isLoading && (
          <div className="absolute inset-6 flex items-center justify-center bg-surface/60 z-[1000] rounded-xl">
            <div className="text-ink-400 text-sm">Loading geographic data…</div>
          </div>
        )}
        <div className="h-full rounded-xl overflow-hidden">
          <MapContainer
            center={[20, 0]}
            zoom={2}
            minZoom={2}
            maxZoom={14}
            worldCopyJump={true}
            scrollWheelZoom={true}
            preferCanvas={true}
            zoomControl={false}
            style={{ height: "100%", width: "100%" }}
            attributionControl={true}
          >
            <ZoomControl position="topright" />
            <TileLayer
              url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
            />
            <ZoomDrivenLayers
              worldData={worldQ.data}
              usaData={usaQ.data}
              indiaData={indiaQ.data}
              citiesData={citiesQ.data}
              regionData={regionQ.data}
              locationsData={locationsQ.data}
              onZoomChange={setZoom}
            />
          </MapContainer>
        </div>
      </div>

      {/* Legend */}
      <div className="px-6 pb-4 flex items-center flex-wrap gap-4 flex-shrink-0">
        <div className="flex items-center gap-2 text-xs text-ink-500">
          <span>Fewer</span>
          {LEGEND_STEPS.map((alpha) => (
            <span
              key={alpha}
              className="inline-block w-5 h-5 rounded"
              style={{ backgroundColor: `rgba(${NAVY[0]},${NAVY[1]},${NAVY[2]},${alpha})` }}
            />
          ))}
          <span>More</span>
        </div>
        {zoom >= 9 && (
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
        )}
      </div>
    </div>
  );
}
