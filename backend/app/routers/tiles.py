"""Map tiles, cached on disk.

`memory_draft.md` §15 asks for "offline OpenStreetMap tiles, pre-cached", and
§13 wants the portal map showing crisis points, helper positions and
allocation lines. Both need a tile source that survives the venue wifi dying,
which is the one condition this whole project assumes will happen.

Rather than a vendor key, the backend proxies OpenStreetMap once and keeps
every tile on disk. After a prefetch the map renders with no internet at all,
which is the honest meaning of "offline": the tiles are actually here, not
merely expected to be in a browser cache that a hard reload would clear.

Two constraints shape this file:

  - **OSM's tile usage policy.** Their tiles are donated infrastructure. A
    valid identifying User-Agent is required, bulk scraping is forbidden, and
    heavy use is supposed to move to a paid provider. So the prefetch is
    bounded to a small bbox and a shallow zoom range, requests are serialised
    with a delay, and everything is cached so a tile is fetched exactly once.

  - **A tile server that fails must not break the portal.** An unreachable
    upstream returns a transparent tile rather than a 500, so the data layers
    still draw over blank ground.
"""

from __future__ import annotations

import asyncio
import logging
import math
from pathlib import Path

import httpx
from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from app.deps import current_admin
from fastapi import Depends

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/tiles", tags=["tiles"])

CACHE = Path(__file__).resolve().parents[2] / "tile_cache"

UPSTREAM = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"

# OSM requires a real identifying User-Agent; the default httpx one is blocked.
HEADERS = {
    "User-Agent": "PACT/0.2 humanitarian-coordination-demo "
                  "(+https://github.com/pact; contact: demo@pact.local)",
}

MAX_ZOOM = 17
MIN_ZOOM = 0

# A single 1x1 transparent PNG. Served when a tile is missing and upstream is
# unreachable, so the map degrades to blank ground with the data still drawn on
# it rather than showing broken-image squares.
_BLANK = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c6300010000050001"
    "0d0a2db40000000049454e44ae426082"
)

_fetch_lock = asyncio.Semaphore(2)


def _path(z: int, x: int, y: int) -> Path:
    return CACHE / str(z) / str(x) / f"{y}.png"


def _valid(z: int, x: int, y: int) -> bool:
    if not (MIN_ZOOM <= z <= MAX_ZOOM):
        return False
    n = 1 << z
    return 0 <= x < n and 0 <= y < n


async def _fetch(z: int, x: int, y: int) -> bytes | None:
    """Fetch one tile upstream and cache it. None when unreachable."""
    async with _fetch_lock:
        try:
            async with httpx.AsyncClient(timeout=10.0, headers=HEADERS) as c:
                r = await c.get(UPSTREAM.format(z=z, x=x, y=y))
            if r.status_code != 200:
                log.debug("tile %s/%s/%s upstream %s", z, x, y, r.status_code)
                return None
            p = _path(z, x, y)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(r.content)
            return r.content
        except Exception as e:
            log.debug("tile %s/%s/%s fetch failed: %s", z, x, y, e)
            return None


@router.get("/{z}/{x}/{y}.png")
async def tile(z: int, x: int, y: int):
    """Serve a tile: disk first, upstream once, blank as a last resort."""
    if not _valid(z, x, y):
        return Response(content=_BLANK, media_type="image/png")

    p = _path(z, x, y)
    if p.exists():
        return Response(content=p.read_bytes(), media_type="image/png",
                        headers={"Cache-Control": "public, max-age=604800",
                                 "X-PACT-Tile": "cache"})

    data = await _fetch(z, x, y)
    if data is None:
        # Never a 500: the portal must still render its data layers.
        return Response(content=_BLANK, media_type="image/png",
                        headers={"X-PACT-Tile": "blank"})
    return Response(content=data, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=604800",
                             "X-PACT-Tile": "upstream"})


# ---------------------------------------------------------------------------
# Prefetch
# ---------------------------------------------------------------------------

def _deg2num(lat: float, lon: float, z: int) -> tuple[int, int]:
    lat_r = math.radians(lat)
    n = 1 << z
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n)
    return x, y


def plan(lat: float, lon: float, radius_km: float,
         zooms: range) -> list[tuple[int, int, int]]:
    """Every (z, x, y) covering a square around a point."""
    # Degrees of latitude are constant; longitude shrinks with cos(lat).
    dlat = radius_km / 111.32
    dlon = radius_km / (111.32 * max(math.cos(math.radians(lat)), 0.01))
    out: list[tuple[int, int, int]] = []
    for z in zooms:
        x0, y0 = _deg2num(lat + dlat, lon - dlon, z)   # north-west
        x1, y1 = _deg2num(lat - dlat, lon + dlon, z)   # south-east
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for y in range(min(y0, y1), max(y0, y1) + 1):
                out.append((z, x, y))
    return out


class PrefetchRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius_km: float = Field(default=8.0, gt=0, le=50)
    min_zoom: int = Field(default=10, ge=0, le=MAX_ZOOM)
    max_zoom: int = Field(default=15, ge=0, le=MAX_ZOOM)
    # A guard, not a preference. Tile counts grow by 4x per zoom level, and
    # OSM's policy forbids bulk downloading; refusing loudly is better than
    # quietly pulling 40,000 tiles off donated infrastructure.
    max_tiles: int = Field(default=3000, ge=1, le=20000)


@router.post("/prefetch", dependencies=[Depends(current_admin)])
async def prefetch(body: PrefetchRequest):
    """Warm the cache for the demo area, so the map works with no internet.

    Run this once after reseeding, on the same coordinates. Tiles already on
    disk are skipped, so re-running is cheap and safe.
    """
    if body.min_zoom > body.max_zoom:
        return {"status": "error", "error": "min_zoom above max_zoom"}

    wanted = plan(body.lat, body.lon, body.radius_km,
                  range(body.min_zoom, body.max_zoom + 1))
    if len(wanted) > body.max_tiles:
        return {"status": "error", "error": "TOO_MANY_TILES",
                "would_fetch": len(wanted), "max_tiles": body.max_tiles,
                "detail": "reduce radius_km or max_zoom; OSM's usage policy "
                          "forbids bulk downloads"}

    missing = [t for t in wanted if not _path(*t).exists()]
    fetched, failed = 0, 0
    for z, x, y in missing:
        if await _fetch(z, x, y) is None:
            failed += 1
        else:
            fetched += 1
        # Deliberate courtesy delay. These are donated servers.
        await asyncio.sleep(0.06)

    return {"status": "ok", "planned": len(wanted), "already_cached":
            len(wanted) - len(missing), "fetched": fetched, "failed": failed,
            "cache_dir": str(CACHE)}


@router.get("/status")
async def tile_status():
    """How much of the map is actually on disk."""
    count, size = 0, 0
    if CACHE.exists():
        for p in CACHE.rglob("*.png"):
            count += 1
            size += p.stat().st_size
    return {"cached_tiles": count, "bytes": size,
            "mb": round(size / 1_048_576, 2),
            "cache_dir": str(CACHE),
            "offline_ready": count > 0}
