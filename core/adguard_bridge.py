"""AdGuard Home REST API wrapper.

All calls go to the AdGuard container.  GuardHome never touches the AdGuard DB
directly — only through this bridge — so the two systems stay in sync.
"""
import os
import httpx
from typing import Optional, List

ADGUARD_URL  = os.getenv("ADGUARD_URL",  "http://localhost:80")
ADGUARD_USER = os.getenv("ADGUARD_USER", "admin")
ADGUARD_PASS = os.getenv("ADGUARD_PASS", "guardhome")


class AdGuardBridge:
    def __init__(self):
        self._base = ADGUARD_URL.rstrip("/")
        self._auth = (ADGUARD_USER, ADGUARD_PASS)

    async def _get(self, path: str, **kwargs):
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{self._base}{path}", auth=self._auth, **kwargs)
            r.raise_for_status()
            return r.json()

    async def _post(self, path: str, json=None, **kwargs):
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{self._base}{path}", auth=self._auth, json=json, **kwargs)
            r.raise_for_status()
            return r

    async def status(self) -> dict:
        return await self._get("/control/status")

    async def get_query_log(self, limit: int = 200) -> list:
        data = await self._get("/control/querylog", params={"limit": limit})
        return data.get("data", [])

    # ── Clients ──────────────────────────────────────────────────────────────

    async def list_clients(self) -> List[dict]:
        data = await self._get("/control/clients")
        return data.get("clients", [])

    async def add_client(self, name: str, ids: List[str], tags: Optional[List[str]] = None,
                         blocked_services: Optional[List[str]] = None,
                         use_global_blocked_services: bool = True) -> None:
        payload = {
            "data": {
                "name": name,
                "ids": ids,
                "use_global_settings": False,
                "use_global_blocked_services": use_global_blocked_services,
                "filtering_enabled": True,
                "safebrowsing_enabled": True,
                "parental_enabled": True,
                "tags": tags or [],
                "blocked_services": blocked_services or [],
            }
        }
        await self._post("/control/clients/add", json=payload)

    async def update_client(self, name: str, data: dict) -> None:
        await self._post("/control/clients/update", json={"name": name, "data": data})

    async def delete_client(self, name: str) -> None:
        await self._post("/control/clients/delete", json={"name": name})

    # ── Filter lists ─────────────────────────────────────────────────────────

    async def list_filters(self) -> List[dict]:
        data = await self._get("/control/filtering/status")
        return data.get("filters", [])

    async def add_filter(self, name: str, url: str, enabled: bool = True) -> None:
        await self._post("/control/filtering/add_url", json={
            "name": name, "url": url, "enabled": enabled,
        })

    async def remove_filter(self, url: str) -> None:
        await self._post("/control/filtering/remove_url", json={"url": url})

    async def set_filter_enabled(self, url: str, enabled: bool) -> None:
        await self._post("/control/filtering/set_url", json={
            "url": url, "enabled": enabled,
        })

    async def refresh_filters(self) -> None:
        await self._post("/control/filtering/refresh", json={"whitelist": False})

    # ── Custom rules ─────────────────────────────────────────────────────────

    async def get_custom_rules(self) -> List[str]:
        data = await self._get("/control/filtering/rules")
        return data.get("rules", [])

    async def set_custom_rules(self, rules: List[str]) -> None:
        await self._post("/control/filtering/set_rules", json={"rules": rules})

    async def add_custom_rule(self, rule: str) -> None:
        current = await self.get_custom_rules()
        if rule not in current:
            current.append(rule)
            await self.set_custom_rules(current)

    async def remove_custom_rule(self, rule: str) -> None:
        current = await self.get_custom_rules()
        if rule in current:
            current.remove(rule)
            await self.set_custom_rules(current)

    # ── DNS rewrites (SafeSearch, YouTube Restricted) ─────────────────────────

    async def list_rewrites(self) -> List[dict]:
        return await self._get("/control/rewrite/list")

    async def add_rewrite(self, domain: str, answer: str) -> None:
        await self._post("/control/rewrite/add", json={"domain": domain, "answer": answer})

    async def delete_rewrite(self, domain: str, answer: str) -> None:
        await self._post("/control/rewrite/delete", json={"domain": domain, "answer": answer})


# ── Module-level convenience functions ───────────────────────────────────────

_bridge = AdGuardBridge()


async def sync_client(device: dict, child_id: Optional[int], db) -> None:
    """Ensure AdGuard has a client entry for this device with the correct filter settings."""
    if not device.get("mac"):
        return
    name = device.get("label") or device.get("hostname") or device["mac"]

    try:
        clients = await _bridge.list_clients()
        existing = next((c for c in clients if device["mac"] in c.get("ids", [])), None)

        # Determine blocked services from child's category rules
        blocked_services = []
        if child_id:
            rows = await db.execute_fetchall(
                "SELECT category, blocked FROM category_rules WHERE child_id=?", (child_id,)
            )
            blocked_services = _categories_to_adguard_services(
                {r["category"]: bool(r["blocked"]) for r in rows}
            )

        if existing:
            await _bridge.update_client(existing["name"], {
                **existing,
                "blocked_services": blocked_services,
                "filtering_enabled": True,
            })
        else:
            await _bridge.add_client(name, [device["mac"]], blocked_services=blocked_services)
    except Exception as exc:
        import logging
        logging.getLogger("guardhome.adguard").warning("sync_client failed: %s", exc)


async def set_client_blocked(mac: str, blocked: bool) -> None:
    """Enable or disable ALL filtering for a device (pause/resume internet)."""
    try:
        clients = await _bridge.list_clients()
        client = next((c for c in clients if mac in c.get("ids", [])), None)
        if client:
            await _bridge.update_client(client["name"], {
                **client,
                "filtering_enabled": blocked,
                "safebrowsing_enabled": blocked,
                "parental_enabled": blocked,
            })
    except Exception as exc:
        import logging
        logging.getLogger("guardhome.adguard").warning("set_client_blocked failed: %s", exc)


async def add_client_allow_rule(mac: str, domain: str) -> None:
    """Add a client-level allow rule (educational exception)."""
    try:
        await _bridge.add_custom_rule(f"@@||{domain}^$client={mac}")
    except Exception as exc:
        import logging
        logging.getLogger("guardhome.adguard").warning("add_client_allow_rule failed: %s", exc)


def _categories_to_adguard_services(rules: dict) -> List[str]:
    """Map GuardHome category names to AdGuard's known blocked services IDs."""
    # AdGuard service IDs: https://github.com/AdguardTeam/AdGuardHome/blob/master/client/src/components/ui/Services.tsx
    MAPPING = {
        "social_media": ["facebook", "instagram", "tiktok", "twitter", "snapchat", "reddit", "pinterest", "tumblr"],
        "gaming": [],  # No direct AdGuard service — handle via filter lists
        "streaming": ["youtube", "twitch", "netflix", "hulu", "disney"],
        "chat_apps": ["discord", "whatsapp", "telegram", "signal"],
    }
    blocked = []
    for category, service_ids in MAPPING.items():
        if rules.get(category, False):
            blocked.extend(service_ids)
    return list(set(blocked))
