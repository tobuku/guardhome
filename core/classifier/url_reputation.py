"""Tier 2 classifier: URL reputation API lookup.

Queries CleanBrowsing or Cloudflare Radar for uncategorized domains.
Results cached locally in SQLite.
"""
import os
import logging
import httpx
import aiosqlite
from typing import Optional
from pathlib import Path

log = logging.getLogger("guardhome.classifier.url_reputation")

DB_PATH = os.getenv("DB_PATH", "/data/guardhome.db")
CLEANBROWSING_KEY = os.getenv("CLEANBROWSING_KEY", "")
CLOUDFLARE_TOKEN  = os.getenv("CLOUDFLARE_TOKEN", "")


async def lookup(domain: str) -> Optional[str]:
    """Return category from reputation API, or None if uncategorized/unavailable.
    Caches result in domain_classifications table."""
    domain = domain.lower().lstrip("www.")

    # Check cache first
    cached = await _get_cached(domain)
    if cached is not None:
        return cached if cached != "" else None

    category = None

    if CLOUDFLARE_TOKEN:
        category = await _cloudflare_radar(domain)
    elif CLEANBROWSING_KEY:
        category = await _cleanbrowsing(domain)

    # Cache (even None = empty string to avoid repeat lookups)
    await _cache_result(domain, category or "", source="url_api")
    return category


async def _cloudflare_radar(domain: str) -> Optional[str]:
    """Query Cloudflare Radar Domain Intelligence API."""
    url = f"https://api.cloudflare.com/client/v4/radar/domains/categorization/{domain}"
    headers = {"Authorization": f"Bearer {CLOUDFLARE_TOKEN}"}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(url, headers=headers)
            r.raise_for_status()
            data = r.json()
            categories = data.get("result", {}).get("content_categories", [])
            if categories:
                return _map_cloudflare_category(categories[0].get("name", ""))
    except Exception as exc:
        log.debug("Cloudflare Radar lookup failed for %s: %s", domain, exc)
    return None


async def _cleanbrowsing(domain: str) -> Optional[str]:
    """Query CleanBrowsing domain reputation API."""
    url = f"https://api.cleanbrowsing.org/app/v2/feeds/domains/?domain={domain}&key={CLEANBROWSING_KEY}"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
            categories = data.get("categories", [])
            if categories:
                return _map_cleanbrowsing_category(categories[0])
    except Exception as exc:
        log.debug("CleanBrowsing lookup failed for %s: %s", domain, exc)
    return None


def _map_cloudflare_category(name: str) -> Optional[str]:
    name = name.lower()
    MAP = {
        "adult themes": "adult",
        "pornography": "adult",
        "gambling": "gambling",
        "violence": "violence",
        "drugs": "drugs",
        "weapons": "violence",
        "extremism": "political_extremism",
    }
    for key, category in MAP.items():
        if key in name:
            return category
    return None


def _map_cleanbrowsing_category(name: str) -> Optional[str]:
    name = name.lower()
    MAP = {
        "adult": "adult",
        "porn": "adult",
        "gambling": "gambling",
        "drugs": "drugs",
        "violence": "violence",
    }
    for key, category in MAP.items():
        if key in name:
            return category
    return None


async def _get_cached(domain: str) -> Optional[str]:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute_fetchall(
                "SELECT category FROM domain_classifications WHERE domain=? AND source='url_api'",
                (domain,),
            )
            if rows:
                return rows[0]["category"]
    except Exception:
        pass
    return None


async def _cache_result(domain: str, category: str, source: str) -> None:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT OR REPLACE INTO domain_classifications (domain, category, source, cached_at)
                   VALUES (?, ?, ?, datetime('now'))""",
                (domain, category, source),
            )
            await db.commit()
    except Exception as exc:
        log.debug("Cache write failed: %s", exc)
