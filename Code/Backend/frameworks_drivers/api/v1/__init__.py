"""Version 1 of the HTTP API."""

from __future__ import annotations

from fastapi import APIRouter

from frameworks_drivers.api.v1 import analyses, health, providers

router = APIRouter()
router.include_router(health.router)
router.include_router(providers.router)
router.include_router(analyses.router)

__all__ = ["router"]
