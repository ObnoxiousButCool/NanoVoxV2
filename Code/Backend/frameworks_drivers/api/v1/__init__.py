"""Version 1 of the HTTP API."""

from __future__ import annotations

from fastapi import APIRouter

from frameworks_drivers.api.v1 import analyses, calls, dashboard, health, providers, taxonomy

router = APIRouter()
router.include_router(health.router)
router.include_router(providers.router)
router.include_router(analyses.router)
router.include_router(calls.router)
router.include_router(dashboard.router)
router.include_router(taxonomy.router)

__all__ = ["router"]
