# hvac-frontend

React 18 + Vite + TailwindCSS dashboard for the HVAC Complaint Intelligence System.

## Purpose

Single-page application with three key views:
- **Alert Banner** — top-of-page live alerts for emerging clusters (60s polling)
- **UMAP Scatter Plot** — 2D visualisation of complaint clusters coloured by sentiment
- **Cluster Detail** — trend sparkline, sentiment stats, one-click Claude advisory

## Quick Start

```bash
cp .env.example .env
npm install
npm run dev
```

Dashboard is available at `http://localhost:5173`. API proxy forwards `/api` to `http://localhost:8000`.

## Build

```bash
npm run build     # outputs to dist/
npm run preview   # preview production build
```

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:8000` |
| `VITE_POLLING_INTERVAL_MS` | Alert polling interval in ms | `60000` |

## Component Overview

| Component | Purpose |
|---|---|
| `AlertBanner` | Top strip showing CRITICAL/HIGH alerts, 60s auto-refresh |
| `UmapScatterPlot` | Plotly scatter with cluster colours and sentiment hover |
| `ClusterSidebar` | Sorted list of clusters with Recharts sparklines |
| `ClusterDetail` | Selected cluster stats + 14-day trend chart + advisory |
| `UploadDropzone` | CSV drag-and-drop uploader → `POST /api/v1/complaints/upload` |
| `AdvisoryModal` | Displays Claude-generated advisory with copy button |
