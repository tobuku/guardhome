from fastapi import APIRouter, Depends, Query
from typing import Optional, List
from datetime import datetime, timedelta

from db.database import get_db
from models.schemas import DnsLogEntry, DailySummary
from auth import get_current_user

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/log", response_model=List[DnsLogEntry])
async def dns_log(
    child_id: Optional[int] = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    blocked_only: bool = False,
    db=Depends(get_db),
    _=Depends(get_current_user),
):
    conditions = []
    params = []
    if child_id is not None:
        conditions.append("child_id=?")
        params.append(child_id)
    if blocked_only:
        conditions.append("blocked=1")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = await db.execute_fetchall(
        f"SELECT * FROM dns_log {where} ORDER BY ts DESC LIMIT ? OFFSET ?",
        (*params, limit, offset),
    )
    return [
        {**dict(r), "blocked": bool(r["blocked"])}
        for r in rows
    ]


@router.get("/summary")
async def daily_summary(
    child_id: Optional[int] = None,
    days: int = Query(7, le=30),
    db=Depends(get_db),
    _=Depends(get_current_user),
):
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    params = [since]
    child_filter = ""
    if child_id is not None:
        child_filter = "AND child_id=?"
        params.append(child_id)

    rows = await db.execute_fetchall(
        f"""SELECT
              date(ts) as date,
              COUNT(*) as total,
              SUM(blocked) as blocked
            FROM dns_log
            WHERE date(ts) >= ? {child_filter}
            GROUP BY date(ts)
            ORDER BY date DESC""",
        params,
    )
    return [dict(r) for r in rows]


@router.get("/top-domains")
async def top_domains(
    child_id: Optional[int] = None,
    limit: int = 20,
    hours: int = 24,
    db=Depends(get_db),
    _=Depends(get_current_user),
):
    since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    params = [since]
    child_filter = ""
    if child_id is not None:
        child_filter = "AND child_id=?"
        params.append(child_id)

    allowed = await db.execute_fetchall(
        f"""SELECT domain, COUNT(*) as hits
            FROM dns_log WHERE ts >= ? AND blocked=0 {child_filter}
            GROUP BY domain ORDER BY hits DESC LIMIT ?""",
        (*params, limit),
    )
    blocked = await db.execute_fetchall(
        f"""SELECT domain, COUNT(*) as hits
            FROM dns_log WHERE ts >= ? AND blocked=1 {child_filter}
            GROUP BY domain ORDER BY hits DESC LIMIT ?""",
        (*params, limit),
    )
    return {
        "top_allowed": [dict(r) for r in allowed],
        "top_blocked": [dict(r) for r in blocked],
    }


@router.get("/coverage")
async def coverage_report(child_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    """Honest Coverage Report — what GuardHome can and cannot see for this child's devices."""
    device_rows = await db.execute_fetchall(
        "SELECT * FROM devices WHERE child_id=?", (child_id,)
    )
    devices = [dict(r) for r in device_rows]

    coverage = []
    for d in devices:
        dt = d.get("device_type", "unknown")
        gaps = _coverage_gaps(dt)
        coverage.append({
            "device": d.get("label") or d.get("hostname") or d["mac"],
            "device_type": dt,
            "can_see": gaps["can"],
            "cannot_see": gaps["cannot"],
        })

    return {
        "child_id": child_id,
        "devices": coverage,
        "universal_gaps": [
            "End-to-end encrypted chat (iMessage, WhatsApp, Signal) — content cannot be read at network level.",
            "In-game voice chat (Roblox, Fortnite, Discord voice) — not monitorable by any consumer product.",
            "Cellular data — if this device has a SIM/LTE, it can bypass all LAN controls.",
        ],
    }


def _coverage_gaps(device_type: str) -> dict:
    base_can = [
        "DNS-level domain blocking",
        "Category-based filtering (adult, violence, gambling, etc.)",
        "Schedule enforcement (bedtime, school hours)",
        "SafeSearch enforcement on Google/Bing",
        "YouTube Restricted Mode",
        "Block attempts logged and reported",
    ]
    if "ios" in device_type.lower() or "ipad" in device_type.lower():
        return {
            "can": base_can + [
                "App installation restrictions (via supervised profile)",
                "VPN installation blocking (via supervised profile)",
                "Personal Hotspot disable (via supervised profile)",
            ],
            "cannot": [
                "iMessage / FaceTime content (end-to-end encrypted)",
                "App Store bypass if device is not supervised",
                "Content inside apps (Reddit, Discord, Twitter, TikTok)",
                "Cellular data usage (bypass all LAN controls)",
            ],
        }
    if "windows" in device_type.lower():
        return {
            "can": base_can + [
                "App usage time tracking (via Windows agent)",
                "Browser history (via Windows agent)",
                "System-level DoH blocking via registry policy",
            ],
            "cannot": [
                "Content within end-to-end encrypted chat apps",
                "Activity if child uses admin account (setup wizard flags this)",
                "In-game chat and voice",
            ],
        }
    return {
        "can": base_can,
        "cannot": [
            "App-level content within encrypted applications",
            "Content if device tunnels over a VPN (alert issued instead)",
        ],
    }
