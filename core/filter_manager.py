"""Manages category-to-filter-list mapping and AdGuard sync.

Filter list strategy:
  - Tier 0 (always on): OISD full, 1Hosts Pro, Hagezi TIF
  - Tier 1 (category toggles): per-category filter lists
  - Bypass hardening: DoH/DoT/VPN blocklists, SafeSearch rewrites
"""
import logging
from typing import Dict, List

from core.adguard_bridge import AdGuardBridge

log = logging.getLogger("guardhome.filter_manager")

# ── Filter list definitions ───────────────────────────────────────────────────

BASE_LISTS = [
    {
        "name": "OISD Full",
        "url": "https://big.oisd.nl/",
        "category": "__base__",
    },
    {
        "name": "1Hosts Pro",
        "url": "https://o0.pages.dev/Pro/adblock.txt",
        "category": "__base__",
    },
    {
        "name": "Hagezi TIF",
        "url": "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/adblock/tif.txt",
        "category": "__base__",
    },
]

CATEGORY_LISTS: Dict[str, List[dict]] = {
    "adult": [
        {
            "name": "StevenBlack Porn",
            "url": "https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/porn/hosts",
        },
        {
            "name": "Hagezi Adult",
            "url": "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/adblock/adult.txt",
        },
    ],
    "violence": [
        {
            "name": "Hagezi Threat Intelligence Feeds",
            "url": "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/adblock/tif.txt",
        },
    ],
    "gore": [
        {
            "name": "GuardHome Gore List",
            "url": "https://raw.githubusercontent.com/guardhome-project/blocklists/main/gore.txt",
        },
    ],
    "gore_anime": [
        {
            "name": "GuardHome Gore Anime",
            "url": "https://raw.githubusercontent.com/guardhome-project/blocklists/main/gore-anime.txt",
        },
    ],
    "gambling": [
        {
            "name": "Hagezi Gambling",
            "url": "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/adblock/gambling.txt",
        },
    ],
    "drugs": [
        {
            "name": "GuardHome Drugs & Alcohol",
            "url": "https://raw.githubusercontent.com/guardhome-project/blocklists/main/drugs.txt",
        },
    ],
    "political_extremism": [
        {
            "name": "GuardHome Political Extremism",
            "url": "https://raw.githubusercontent.com/guardhome-project/blocklists/main/extremism.txt",
        },
    ],
    "self_harm": [
        {
            "name": "GuardHome Self Harm",
            "url": "https://raw.githubusercontent.com/guardhome-project/blocklists/main/self-harm.txt",
        },
    ],
    "vpn": [
        {
            "name": "GuardHome VPN Bypass Domains",
            "url": "https://raw.githubusercontent.com/guardhome-project/blocklists/main/vpn-bypass.txt",
        },
    ],
}

# DNS rewrites for SafeSearch and Restricted Mode
SAFESEARCH_REWRITES = [
    ("www.google.com",    "forcesafesearch.google.com"),
    ("www.bing.com",      "strict.bing.com"),
    ("duckduckgo.com",    "safe.duckduckgo.com"),
]

YOUTUBE_RESTRICTED_REWRITES = [
    ("www.youtube.com", "restrict.youtube.com"),
    ("m.youtube.com",   "restrict.youtube.com"),
    ("youtubei.googleapis.com", "restrict.youtube.com"),
]

# DoH bypass hardening — block known DoH providers
DOH_BLOCK_RULES = [
    # Firefox canary — causes Firefox to disable DoH automatically
    "||use-application-dns.net^",
    # iCloud Private Relay
    "||mask.icloud.com^",
    "||mask-h2.icloud.com^",
    # Known DoH resolvers
    "||cloudflare-dns.com^",
    "||dns.google^",
    "||doh.opendns.com^",
    "||dns.quad9.net^",
    "||doh.cleanbrowsing.org^",
    "||dns.nextdns.io^",
]


bridge = AdGuardBridge()


async def apply_base_lists() -> None:
    """Ensure all baseline filter lists are installed (idempotent)."""
    try:
        current_filters = await bridge.list_filters()
        current_urls = {f["url"] for f in current_filters}
        for fl in BASE_LISTS:
            if fl["url"] not in current_urls:
                log.info("Adding base filter list: %s", fl["name"])
                await bridge.add_filter(fl["name"], fl["url"])
    except Exception as exc:
        log.error("apply_base_lists failed: %s", exc)


async def apply_bypass_hardening() -> None:
    """Add DoH/iCloud-Relay/VPN bypass blocking rules."""
    try:
        current = set(await bridge.get_custom_rules())
        new_rules = [r for r in DOH_BLOCK_RULES if r not in current]
        if new_rules:
            await bridge.set_custom_rules(list(current) + new_rules)
            log.info("Added %d bypass hardening rules.", len(new_rules))
    except Exception as exc:
        log.error("apply_bypass_hardening failed: %s", exc)


async def apply_safesearch(youtube_restricted: bool = True) -> None:
    """Enable SafeSearch and YouTube Restricted Mode via DNS rewrites."""
    try:
        existing = {(r["domain"], r["answer"]) for r in await bridge.list_rewrites()}
        rewrites = SAFESEARCH_REWRITES.copy()
        if youtube_restricted:
            rewrites += YOUTUBE_RESTRICTED_REWRITES
        for domain, answer in rewrites:
            if (domain, answer) not in existing:
                log.info("Adding DNS rewrite: %s → %s", domain, answer)
                await bridge.add_rewrite(domain, answer)
    except Exception as exc:
        log.error("apply_safesearch failed: %s", exc)


async def sync_category_lists(categories: Dict[str, bool]) -> None:
    """Enable or disable filter lists based on a dict of {category: blocked}."""
    try:
        current_filters = await bridge.list_filters()
        current_map = {f["url"]: f for f in current_filters}
        for category, blocked in categories.items():
            if category not in CATEGORY_LISTS:
                continue
            for fl in CATEGORY_LISTS[category]:
                if fl["url"] in current_map:
                    if current_map[fl["url"]]["enabled"] != blocked:
                        await bridge.set_filter_enabled(fl["url"], blocked)
                elif blocked:
                    await bridge.add_filter(fl["name"], fl["url"], enabled=True)
    except Exception as exc:
        log.error("sync_category_lists failed: %s", exc)


async def sync_child_rules(child_id: int, db) -> None:
    """After a category toggle for one child, push their rules to AdGuard."""
    rows = await db.execute_fetchall(
        "SELECT category, blocked FROM category_rules WHERE child_id=?", (child_id,)
    )
    categories = {r["category"]: bool(r["blocked"]) for r in rows}
    # For simplicity in MVP, category lists are global (affect all clients).
    # Phase 2: per-client filtering via AdGuard client profiles.
    await sync_category_lists(categories)


async def sync_all_rules(db) -> None:
    """Full sync on startup / wizard completion."""
    await apply_base_lists()
    await apply_bypass_hardening()
    await apply_safesearch()

    # Merge all children's rules into a unified "max restriction" pass
    rows = await db.execute_fetchall("SELECT DISTINCT category FROM category_rules WHERE blocked=1")
    all_blocked = {r["category"]: True for r in rows}
    await sync_category_lists(all_blocked)
    log.info("Full rule sync complete.")
