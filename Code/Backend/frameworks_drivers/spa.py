"""Serve the built frontend from the API process.

One process and one origin, which removes a surprising amount: no CORS, no
separate web server, no SPA fallback rule to configure, and no rebuilding the
bundle when the API's address changes — it becomes a relative path.

Mounted only when a build is actually present. In development the frontend is
served by Vite on its own port, and the absence of ``dist`` is the normal state
rather than a misconfiguration.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

INDEX = "index.html"

# Vite fingerprints asset filenames, so a given URL's content never changes and
# can be cached hard. index.html must not be, or a browser holding a cached copy
# would keep loading the previous build's assets after a deployment.
_ASSET_CACHE = "public, max-age=31536000, immutable"
_INDEX_CACHE = "no-cache, no-store, must-revalidate"


def mount_frontend(app: FastAPI, dist: Path, *, api_prefix: str) -> bool:
    """Serve ``dist`` from this app. Returns whether anything was mounted.

    The catch-all is registered last so every API route is matched first, and it
    refuses paths under the API prefix outright: an unknown endpoint must answer
    404, not hand the caller a page of HTML that their JSON parser will choke on.
    """
    index = dist / INDEX
    if not index.is_file():
        logger.info(
            "No frontend build at %s; serving the API only.",
            dist,
            extra={"frontend_dist": str(dist)},
        )
        return False

    # Everything goes through one handler rather than mounting StaticFiles for
    # /assets: a mount serves files without the cache headers set below, which
    # is precisely backwards — the hashed assets are the cacheable half.
    @app.get("/{requested:path}", include_in_schema=False)
    async def serve_spa(requested: str) -> FileResponse:
        if f"/{requested}".startswith(api_prefix):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        candidate = _resolve(dist, requested)
        if candidate is None or candidate == index.resolve():
            # No file behind it: a client-side route such as /calls, which the
            # app reads for itself once loaded. index.html is never cached, or a
            # browser holding one would keep loading the previous build.
            return FileResponse(index, headers={"Cache-Control": _INDEX_CACHE})

        return FileResponse(candidate, headers={"Cache-Control": _ASSET_CACHE})

    logger.info("Serving frontend from %s", dist, extra={"frontend_dist": str(dist)})
    return True


def _resolve(dist: Path, requested: str) -> Path | None:
    """The real file for a request, or ``None`` if there isn't one.

    Resolved and re-checked against the root because ``requested`` is attacker
    controlled: without it, ``../../.env`` would be served happily.
    """
    if not requested:
        return None
    try:
        candidate = (dist / requested).resolve()
    except (OSError, ValueError):
        return None
    if not candidate.is_file():
        return None
    root = dist.resolve()
    return candidate if root == candidate or root in candidate.parents else None
