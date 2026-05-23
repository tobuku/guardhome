from fastapi import APIRouter, Depends, HTTPException
from typing import List

from db.database import get_db
from models.schemas import ScheduleCreate, ScheduleOut, AllowException, AllowExceptionOut
from auth import get_current_user

router = APIRouter(prefix="/api/rules", tags=["rules"])


# ── Schedules ─────────────────────────────────────────────────────────────────

@router.get("/{child_id}/schedules", response_model=List[ScheduleOut])
async def list_schedules(child_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    rows = await db.execute_fetchall(
        "SELECT * FROM schedules WHERE child_id=?", (child_id,)
    )
    result = []
    for r in rows:
        d = dict(r)
        import json
        d["days"] = json.loads(d["days"])
        d["enabled"] = bool(d["enabled"])
        result.append(d)
    return result


@router.post("/{child_id}/schedules", response_model=ScheduleOut, status_code=201)
async def create_schedule(child_id: int, body: ScheduleCreate, db=Depends(get_db), _=Depends(get_current_user)):
    import json
    cursor = await db.execute(
        "INSERT INTO schedules (child_id, name, days, start_time, end_time, action, enabled) VALUES (?,?,?,?,?,?,?)",
        (child_id, body.name, json.dumps(body.days), body.start_time, body.end_time, body.action, int(body.enabled)),
    )
    await db.commit()
    rows = await db.execute_fetchall("SELECT * FROM schedules WHERE id=?", (cursor.lastrowid,))
    d = dict(rows[0])
    d["days"] = json.loads(d["days"])
    d["enabled"] = bool(d["enabled"])
    return d


@router.patch("/{child_id}/schedules/{schedule_id}", response_model=ScheduleOut)
async def update_schedule(child_id: int, schedule_id: int, body: ScheduleCreate, db=Depends(get_db), _=Depends(get_current_user)):
    import json
    await db.execute(
        "UPDATE schedules SET name=?,days=?,start_time=?,end_time=?,action=?,enabled=? WHERE id=? AND child_id=?",
        (body.name, json.dumps(body.days), body.start_time, body.end_time, body.action, int(body.enabled), schedule_id, child_id),
    )
    await db.commit()
    rows = await db.execute_fetchall("SELECT * FROM schedules WHERE id=?", (schedule_id,))
    if not rows:
        raise HTTPException(404, "Schedule not found")
    d = dict(rows[0])
    d["days"] = json.loads(d["days"])
    d["enabled"] = bool(d["enabled"])
    return d


@router.delete("/{child_id}/schedules/{schedule_id}", status_code=204)
async def delete_schedule(child_id: int, schedule_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    await db.execute("DELETE FROM schedules WHERE id=? AND child_id=?", (schedule_id, child_id))
    await db.commit()


# ── Educational Exceptions ────────────────────────────────────────────────────

@router.get("/{child_id}/exceptions", response_model=List[AllowExceptionOut])
async def list_exceptions(child_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    rows = await db.execute_fetchall("SELECT * FROM allow_exceptions WHERE child_id=?", (child_id,))
    return [dict(r) for r in rows]


@router.post("/{child_id}/exceptions", response_model=AllowExceptionOut, status_code=201)
async def add_exception(child_id: int, body: AllowException, db=Depends(get_db), _=Depends(get_current_user)):
    try:
        cursor = await db.execute(
            "INSERT INTO allow_exceptions (child_id, domain, label) VALUES (?,?,?)",
            (child_id, body.domain.lower().strip(), body.label),
        )
        await db.commit()
    except Exception:
        raise HTTPException(409, "Domain already in exceptions list")

    # Tell AdGuard to always allow this domain for this client
    from core.adguard_bridge import add_client_allow_rule
    device_rows = await db.execute_fetchall("SELECT mac FROM devices WHERE child_id=?", (child_id,))
    for d in device_rows:
        await add_client_allow_rule(d["mac"], body.domain)

    rows = await db.execute_fetchall("SELECT * FROM allow_exceptions WHERE id=?", (cursor.lastrowid,))
    return dict(rows[0])


@router.delete("/{child_id}/exceptions/{exception_id}", status_code=204)
async def remove_exception(child_id: int, exception_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    await db.execute("DELETE FROM allow_exceptions WHERE id=? AND child_id=?", (exception_id, child_id))
    await db.commit()
