"""Tier 3 classifier: AI/ML content classification for novel domains.

When Tiers 1 and 2 return no result, this module fetches the page and
classifies it using either:
  - A local ONNX model (zero-cost, works offline on Pi)
  - Claude API (higher accuracy, requires ANTHROPIC_API_KEY env var)

Results are cached. Parent can correct misclassifications from the dashboard.
"""
import os
import logging
import httpx
import aiosqlite
from typing import Optional

log = logging.getLogger("guardhome.classifier.ai")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DB_PATH = os.getenv("DB_PATH", "/data/guardhome.db")
MAX_PAGE_CHARS = 3000  # Limit sent to classifier


async def classify(domain: str) -> Optional[str]:
    """Fetch page content and classify into a GuardHome category.
    Returns category string or None if content is benign/unclassifiable."""

    # Check cache (parent overrides first)
    cached = await _get_cached(domain)
    if cached is not None:
        return cached if cached != "" else None

    # Fetch page text
    text = await _fetch_text(domain)
    if not text:
        return None

    category = None
    if ANTHROPIC_API_KEY:
        category = await _classify_with_claude(domain, text)
    else:
        category = await _classify_with_keywords(text)

    await _cache_result(domain, category or "", source="ai", confidence=0.8)

    if category:
        log.info("AI classified %s as '%s'", domain, category)
        # Dynamically add AdGuard block rule
        from core.adguard_bridge import AdGuardBridge
        bridge = AdGuardBridge()
        await bridge.add_custom_rule(f"||{domain}^")

    return category


async def _fetch_text(domain: str) -> Optional[str]:
    """Fetch the domain's homepage and return plain text (truncated)."""
    for scheme in ("https://", "http://"):
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                r = await client.get(f"{scheme}{domain}", headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200:
                    content_type = r.headers.get("content-type", "")
                    if "text/html" in content_type:
                        return _strip_html(r.text[:MAX_PAGE_CHARS * 5])
        except Exception:
            pass
    return None


def _strip_html(html: str) -> str:
    """Very basic HTML → text stripping (no library dependency)."""
    import re
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>",  " ", text,  flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text[:MAX_PAGE_CHARS].strip()


async def _classify_with_claude(domain: str, page_text: str) -> Optional[str]:
    """Use Claude API for high-accuracy classification."""
    system_prompt = (
        "You are a content safety classifier for a parental control system. "
        "Given a website's domain and a snippet of its page text, classify it into "
        "exactly ONE of the following categories if the content is harmful or inappropriate:\n\n"
        "adult, violence, gore, gore_anime, gambling, drugs, political_extremism, self_harm, vpn\n\n"
        "If the content is benign, respond with: none\n"
        "Respond with ONLY the category name — no explanation."
    )
    user_prompt = f"Domain: {domain}\n\nPage text:\n{page_text}"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 10,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                },
            )
            r.raise_for_status()
            result = r.json()["content"][0]["text"].strip().lower()
            return None if result == "none" else result
    except Exception as exc:
        log.warning("Claude classification failed for %s: %s", domain, exc)
        return None


async def _classify_with_keywords(page_text: str) -> Optional[str]:
    """Lightweight keyword-based fallback (no API or model required)."""
    text = page_text.lower()
    KEYWORD_MAP = {
        "adult":             ["pornography", "explicit content", "xxx", "nude", "naked", "erotic"],
        "gore":              ["gore", "graphic violence", "decapitation", "splatter", "gory"],
        "gore_anime":        ["gore anime", "ero guro", "guro", "torture hentai"],
        "gambling":          ["casino", "poker", "bet365", "sports betting", "place your bets"],
        "drugs":             ["buy cocaine", "buy meth", "buy marijuana online", "drug marketplace"],
        "political_extremism": ["white supremacy", "nazi", "jihad recruitment", "ethnic cleansing"],
        "self_harm":         ["how to cut yourself", "pro-ana", "thinspo", "suicide method"],
        "vpn":               ["anonymous vpn", "bypass censorship", "hide your ip", "no-log vpn"],
    }
    scores = {}
    for category, keywords in KEYWORD_MAP.items():
        hits = sum(1 for kw in keywords if kw in text)
        if hits:
            scores[category] = hits
    return max(scores, key=scores.get) if scores else None


async def _get_cached(domain: str) -> Optional[str]:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute_fetchall(
                "SELECT category FROM domain_classifications WHERE domain=?", (domain,)
            )
            if rows:
                return rows[0]["category"]
    except Exception:
        pass
    return None


async def _cache_result(domain: str, category: str, source: str, confidence: float = 0.0) -> None:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT OR REPLACE INTO domain_classifications
                   (domain, category, confidence, source, cached_at)
                   VALUES (?, ?, ?, ?, datetime('now'))""",
                (domain, category, confidence, source),
            )
            await db.commit()
    except Exception as exc:
        log.debug("Cache write failed: %s", exc)
