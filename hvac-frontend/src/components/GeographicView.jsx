import { useState, useEffect } from "react";
import GeoChoroplethMap from "./GeoChoroplethMap";
import BoroughMap from "./BoroughMap";
import { useGeo } from "../hooks/useAnalytics";
import worldGeoRaw from "../data/world_countries.json";
import usaGeoRaw from "../data/us_states.json";

const STORAGE_KEY = "hvac_geo_view";
const VIEWS = ["world", "usa", "nyc"];

// Full state name → 2-letter postal code, matching the PublicaMundi GeoJSON
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
  "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
  "Puerto Rico": "PR",
};

function getWorldKey(feature) {
  return feature.properties?.ISO_A3 ?? "";
}

function getUsaKey(feature) {
  const name = feature.properties?.name ?? "";
  return STATE_NAME_TO_CODE[name] ?? name;
}

const VIEW_CONFIG = {
  world: {
    label: "World",
    center: [20, 10],
    zoom: 2,
    title: "Global Complaint Volume",
    caption: "Complaint density across Carrier's worldwide service footprint. Darker shading = higher volume.",
    getKey: getWorldKey,
  },
  usa: {
    label: "USA",
    center: [39, -96],
    zoom: 4,
    title: "US State Complaint Volume",
    caption: "Complaint volume by US state. New York includes real NYC 311 data.",
    getKey: getUsaKey,
  },
};

function SegmentedControl({ value, onChange }) {
  return (
    <div className="bg-ink-100 p-0.5 rounded-lg flex items-center gap-0.5">
      {VIEWS.map((v) => (
        <button
          key={v}
          onClick={() => onChange(v)}
          className={[
            "px-3 py-1 text-sm font-medium rounded-md transition-colors",
            value === v
              ? "bg-surface text-ink-900 shadow-sm"
              : "text-ink-500 hover:text-ink-900",
          ].join(" ")}
        >
          {v === "nyc" ? "NYC" : VIEW_CONFIG[v].label}
        </button>
      ))}
    </div>
  );
}

export default function GeographicView() {
  const [view, setView] = useState(
    () => localStorage.getItem(STORAGE_KEY) ?? "world"
  );

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, view);
  }, [view]);

  const geoQ = useGeo(view);

  const cfg = VIEW_CONFIG[view];

  return (
    <div className="h-full flex flex-col gap-0">
      <div className="flex justify-end px-6 pt-4 pb-2 flex-shrink-0">
        <SegmentedControl value={view} onChange={setView} />
      </div>

      <div className="flex-1 min-h-0 px-6 pb-6">
        {view === "nyc" ? (
          <BoroughMap />
        ) : (
          <GeoChoroplethMap
            geoData={view === "world" ? worldGeoRaw : usaGeoRaw}
            regions={geoQ.data?.regions}
            maxCount={geoQ.data?.max_count}
            total={geoQ.data?.total}
            center={cfg.center}
            zoom={cfg.zoom}
            getKey={cfg.getKey}
            title={cfg.title}
            caption={cfg.caption}
            isLoading={geoQ.isLoading}
            isError={geoQ.isError}
          />
        )}
      </div>
    </div>
  );
}
