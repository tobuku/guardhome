"""Tier 1 classifier: instant domain-list lookup (no network call needed).

Loads a curated community category→domain mapping into memory on first import.
Falls back to a simple suffix-match against category-tagged domain lists.
"""
import os
import asyncio
import logging
from typing import Optional, Dict, Set
from pathlib import Path

import httpx

log = logging.getLogger("guardhome.classifier.domain_lookup")

# Local cache directory for downloaded domain lists
LISTS_DIR = Path(os.getenv("LISTS_DIR", "/data/lists"))

TAGGED_LISTS = {
    "adult": [
        "https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/porn/hosts",
    ],
    "gambling": [
        "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/domains/gambling.txt",
    ],
    "gore": [
        "https://raw.githubusercontent.com/guardhome-project/blocklists/main/gore-domains.txt",
    ],
    "gore_anime": [
        "https://raw.githubusercontent.com/guardhome-project/blocklists/main/gore-anime-domains.txt",
    ],
}

_category_sets: Dict[str, Set[str]] = {}
_loaded = False
_load_lock = asyncio.Lock()


async def ensure_loaded() -> None:
    global _loaded
    async with _load_lock:
        if _loaded:
            return
        LISTS_DIR.mkdir(parents=True, exist_ok=True)
        for category, urls in TAGGED_LISTS.items():
            _category_sets[category] = set()
            for url in urls:
                await _load_url(category, url)
        _loaded = True
        log.info("Domain lookup lists loaded: %s categories", len(_category_sets))


async def _load_url(category: str, url: str) -> None:
    """Download (or use cached) domain list and add entries to the category set."""
    filename = LISTS_DIR / f"{category}_{url.split('/')[-1]}"
    if not filename.exists():
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get(url)
                r.raise_for_status()
                filename.write_bytes(r.content)
            log.info("Downloaded %s for category '%s'", url, category)
        except Exception as exc:
            log.warning("Failed to download %s: %s", url, exc)
            return

    try:
        for line in filename.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # hosts file format: "0.0.0.0 example.com" or plain "example.com"
            parts = line.split()
            domain = parts[-1].lower().lstrip("www.")
            if "." in domain:
                _category_sets[category].add(domain)
    except Exception as exc:
        log.warning("Failed to parse %s: %s", filename, exc)


async def lookup(domain: str) -> Optional[str]:
    """Return category name if domain matches a known list, else None."""
    await ensure_loaded()
    d = domain.lower().lstrip("www.")
    for category, domains in _category_sets.items():
        if d in domains:
            return category
        # Suffix match: "sub.example.com" → "example.com"
        parts = d.split(".")
        for i in range(1, len(parts) - 1):
            suffix = ".".join(parts[i:])
            if suffix in domains:
                return category
    return None
