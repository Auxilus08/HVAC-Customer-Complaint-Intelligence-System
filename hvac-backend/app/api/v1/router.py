"""APIRouter aggregating all v1 route modules."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import alerts, analytics, clusters, complaints, health, search, umap

v1_router = APIRouter(prefix="/api/v1")

v1_router.include_router(health.router)
v1_router.include_router(search.router)
v1_router.include_router(complaints.router)
v1_router.include_router(clusters.router)
v1_router.include_router(umap.router)
v1_router.include_router(alerts.router)
v1_router.include_router(analytics.router)
