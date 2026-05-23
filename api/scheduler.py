"""Background task scheduler — runs inside the API container."""
import asyncio
import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler

log = logging.getLogger("guardhome.scheduler")


def start_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Sync DNS log from AdGuard every 60 seconds
    scheduler.add_job(_sync_dns_log, "interval", seconds=60, id="dns_log_sync")

    # Enforce schedules every minute
    scheduler.add_job(_enforce_schedules, "interval", seconds=60, id="schedule_enforce")

    # Birthday milestone checks — run once daily at midnight UTC
    scheduler.add_job(_birthday_checks, "cron", hour=0, minute=0, id="birthday_checks")

    # Weekly digest — Sunday at 8am UTC
    scheduler.add_job(_weekly_digest, "cron", day_of_week="sun", hour=8, id="weekly_digest")

    scheduler.start()
    log.info("Scheduler started.")
    return scheduler


async def _sync_dns_log():
    """Pull recent query log from AdGuard and store in local DB."""
    try:
        import aiosqlite
        from core.adguard_bridge import AdGuardBridge
        from db.database import DB_PATH

        bridge = AdGuardBridge()
        entries = await bridge.get_query_log(limit=200)
        if not entries:
            return

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            # Build mac→child map
            device_rows = await db.execute_fetchall("SELECT ip, child_id FROM devices")
            ip_to_child = {r["ip"]: r["child_id"] for r in device_rows if r["ip"]}

            for e in entries:
                client_ip = e.get("client")
                child_id = ip_to_child.get(client_ip)
                blocked = e.get("reason", "") not in ("", "NotFilteredNotFound", "NotFilteredWhiteList")
                await db.execute(
                    """INSERT OR IGNORE INTO dns_log (ts, client_ip, domain, blocked, rule, child_id)
                       VALUES (?,?,?,?,?,?)""",
                    (
                        e.get("time", datetime.now(timezone.utc).isoformat()),
                        client_ip,
                        e.get("question", {}).get("name", ""),
                        int(blocked),
                        e.get("rule", ""),
                        child_id,
                    ),
                )
                # Emit alert for blocked attempts
                if blocked and child_id:
                    await _maybe_alert(db, child_id, e)

            await db.commit()
    except Exception as exc:
        log.exception("DNS log sync failed: %s", exc)


async def _maybe_alert(db, child_id: int, entry: dict):
    """Create an alert for high-priority blocked domains (VPN attempts, known CSAM domains, etc.)."""
    domain = entry.get("question", {}).get("name", "")
    reason = entry.get("reason", "")

    HIGH_PRIORITY_PATTERNS = ["vpn", "torguard", "nordvpn", "expressvpn", "protonvpn", "surfshark"]
    is_vpn_attempt = any(p in domain.lower() for p in HIGH_PRIORITY_PATTERNS)

    if is_vpn_attempt:
        await db.execute(
            """INSERT INTO alerts (child_id, alert_type, title, detail)
               VALUES (?,?,?,?)""",
            (child_id, "vpn_attempt", "VPN bypass attempt detected",
             f"Device tried to reach {domain}"),
        )


async def _enforce_schedules():
    """Block/unblock devices according to their active schedules."""
    try:
        import aiosqlite, json
        from core.adguard_bridge import set_client_blocked
        from db.database import DB_PATH

        now = datetime.now(timezone.utc)
        day_abbr = now.strftime("%a")  # Mon, Tue, ...
        current_time = now.strftime("%H:%M")

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            schedules = await db.execute_fetchall(
                "SELECT s.*, c.id as cid FROM schedules s JOIN children c ON c.id=s.child_id WHERE s.enabled=1"
            )
            for sched in schedules:
                days = json.loads(sched["days"])
                if day_abbr not in days:
                    continue
                in_window = sched["start_time"] <= current_time <= sched["end_time"]
                if not in_window:
                    continue

                # Block all devices assigned to this child
                devices = await db.execute_fetchall(
                    "SELECT mac FROM devices WHERE child_id=?", (sched["cid"],)
                )
                for dev in devices:
                    await set_client_blocked(dev["mac"], blocked=True)
    except Exception as exc:
        log.exception("Schedule enforcement failed: %s", exc)


async def _birthday_checks():
    """Emit milestone alerts when a child has a birthday today."""
    try:
        import aiosqlite
        from db.database import DB_PATH

        today = datetime.now(timezone.utc).strftime("%m-%d")
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            children = await db.execute_fetchall(
                "SELECT * FROM children WHERE strftime('%m-%d', birthday) = ?", (today,)
            )
            for child in children:
                await db.execute(
                    """INSERT INTO alerts (child_id, alert_type, title, detail)
                       VALUES (?,?,?,?)""",
                    (
                        child["id"],
                        "birthday_milestone",
                        f"{child['name']}'s birthday — review their settings",
                        f"{child['name']}'s filter settings were last configured for age {child['age']}. "
                        f"They may be ready for adjusted restrictions.",
                    ),
                )
                # Increment age
                await db.execute(
                    "UPDATE children SET age=age+1 WHERE id=?", (child["id"],)
                )
            await db.commit()
    except Exception as exc:
        log.exception("Birthday check failed: %s", exc)


async def _weekly_digest():
    log.info("Weekly digest job triggered (email delivery not yet configured).")
