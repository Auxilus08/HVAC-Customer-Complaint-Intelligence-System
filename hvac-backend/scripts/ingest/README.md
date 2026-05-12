# Ingest Adapters

Four adapters pull real complaint and building data into the HVAC Intelligence System.
Run all of them with:

```bash
make ingest-all
```

Adapters run **inside the backend container** (deps baked into the image).

---

## NYC 311 — Heat/Hot Water and Air Quality complaints

**Source:** [NYC Open Data Socrata](https://data.cityofnewyork.us/resource/erm2-nwe9.json)
**ToS:** Open data, free and unrestricted for commercial/research use.
**Volume:** ~8–12K records per 5-year window

```bash
make ingest-nyc
# or directly:
docker exec hvac_backend python -m scripts.ingest.nyc_311 --limit 10000 --window-days 1825
```

**PLUTO CSV requirement:** To filter complaints to commercial buildings only,
provide a one-column BBL lookup generated from the NYC PLUTO dataset:

1. Download PLUTO from https://www.nyc.gov/site/planning/data-maps/open-data/dwn-pluto-mappluto.page
2. Filter rows where `BldgClass` starts with `O`, `K`, `H`, `RB`, or `M`
3. Save as `data/pluto_commercial_bbls.csv` (columns: `bbl`, `bldgclass`)
4. Pass `--pluto-csv data/pluto_commercial_bbls.csv`

Without the CSV the adapter runs without the BBL filter (all HVAC-relevant 311 records are ingested).

---

## CPSC SaferProducts — Federal product safety incidents

**Source:** [SaferProducts.gov REST API](https://www.saferproducts.gov/RestWebServices/)
**ToS:** US federal government open data, public domain.
**Volume:** ~200–800 records (Carrier, Bryant, ICP)

```bash
make ingest-cpsc
# or directly:
docker exec hvac_backend python -m scripts.ingest.cpsc --limit 1000
docker exec hvac_backend python -m scripts.ingest.cpsc --manufacturers Carrier,Bryant,ICP,Toshiba-Carrier
```

---

## App Store Reviews — Carrier mobile apps

**Source:** Google Play (via `google-play-scraper`) and Apple App Store (via `app-store-scraper`)
**ToS:** Both libraries scrape public review data; respect per-library documentation.
**Volume:** ~500–2000 reviews across four apps

```bash
make ingest-apps
# or directly:
docker exec hvac_backend python -m scripts.ingest.app_store --limit-per-app 500
```

Includes Hinglish detection — reviews from Carrier eService India (`com.carrier.eservice`)
are tagged `language=hi-en` when they mix Hindi words into English text.

---

## BDG2 — Commercial Building Metadata

**Source:** [Building Data Genome Project 2](https://github.com/buds-lab/building-data-genome-project-2)
**ToS:** Open research dataset, MIT-licensed. Cite: Miller et al., 2020.
**Volume:** ~1,600 commercial buildings

Writes to `commercial_buildings` reference table (not complaints). No PII strip or Celery enqueue.
Used to enrich cluster analytics with `primary_use`, `sqft`, and EUI.

```bash
make ingest-bdg2
# or directly:
docker exec hvac_backend python -m scripts.ingest.bdg2
docker exec hvac_backend python -m scripts.ingest.bdg2 --no-filter   # all building types
```

---

## Full pipeline after ingest

```bash
make ingest-all          # fetch all four sources
# Wait for Celery embedding queue to drain (~3-5 min for 12K complaints)
make cluster             # UMAP + HDBSCAN on new volume
make label-job           # LLM labels each cluster
make demo-check          # smoke test
```

Check analytics endpoints:
```bash
curl http://localhost:8000/api/v1/analytics/sources | jq .
curl http://localhost:8000/api/v1/analytics/buildings | jq .
```
