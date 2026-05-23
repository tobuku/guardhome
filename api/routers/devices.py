from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional

from db.database import get_db
from models.schemas import DeviceOut, DeviceAssign
from auth import get_current_user

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.get("", response_model=List[DeviceOut])
async def list_devices(db=Depends(get_db), _=Depends(get_current_user)):
    rows = await db.execute_fetchall("SELECT * FROM devices ORDER BY last_seen DESC")
    return [dict(r) for r in rows]


@router.get("/scan")
async def scan_lan(db=Depends(get_db), _=Depends(get_current_user)):
    """Trigger a LAN ARP scan to discover new devices."""
    from core.device_scanner import scan_lan as do_scan
    discovered = await do_scan()
    # Upsert into DB
    for device in discovered:
        await db.execute(
            """INSERT INTO devices (mac, hostname, ip, last_seen)
               VALUES (?,?,?,datetime('now'))
               ON CONFLICT(mac) DO UPDATE SET
                 ip=excluded.ip,
                 hostname=COALESCE(excluded.hostname, hostname),
                 last_seen=excluded.last_seen""",
            (device["mac"], device.get("hostname"), device.get("ip")),
        )
    await db.commit()
    rows = await db.execute_fetchall("SELECT * FROM devices ORDER BY last_seen DESC")
    return {"scanned": len(discovered), "devices": [dict(r) for r in rows]}


@router.patch("/{device_id}", response_model=DeviceOut)
async def assign_device(device_id: int, body: DeviceAssign, db=Depends(get_db), _=Depends(get_current_user)):
    rows = await db.execute_fetchall("SELECT * FROM devices WHERE id=?", (device_id,))
    if not rows:
        raise HTTPException(404, "Device not found")

    await db.execute(
        "UPDATE devices SET child_id=?, label=COALESCE(?,label) WHERE id=?",
        (body.child_id, body.label, device_id),
    )
    await db.commit()

    # Sync AdGuard client list
    from core.adguard_bridge import sync_client
    device = dict((await db.execute_fetchall("SELECT * FROM devices WHERE id=?", (device_id,)))[0])
    await sync_client(device, body.child_id, db)

    rows = await db.execute_fetchall("SELECT * FROM devices WHERE id=?", (device_id,))
    return dict(rows[0])


@router.post("/{device_id}/pause")
async def pause_device(device_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    """Block all DNS for this device immediately."""
    rows = await db.execute_fetchall("SELECT * FROM devices WHERE id=?", (device_id,))
    if not rows:
        raise HTTPException(404, "Device not found")
    device = dict(rows[0])

    from core.adguard_bridge import set_client_blocked
    await set_client_blocked(device["mac"], blocked=True)
    return {"ok": True, "mac": device["mac"], "paused": True}


@router.post("/{device_id}/resume")
async def resume_device(device_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    rows = await db.execute_fetchall("SELECT * FROM devices WHERE id=?", (device_id,))
    if not rows:
        raise HTTPException(404, "Device not found")
    device = dict(rows[0])

    from core.adguard_bridge import set_client_blocked
    await set_client_blocked(device["mac"], blocked=False)
    return {"ok": True, "mac": device["mac"], "paused": False}
