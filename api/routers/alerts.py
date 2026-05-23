from fastapi import APIRouter, Depends, Query
from typing import Optional, List

from db.database import get_db
from models.schemas import AlertOut
from auth import get_current_user

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=List[AlertOut])
async def list_alerts(
    child_id: Optional[int] = None,
    unread_only: bool = False,
    limit: int = Query(50, le=200),
    db=Depends(get_db),
    _=Depends(get_current_user),
):
    conditions = []
    params = []
    if child_id is not None:
        conditions.append("child_id=?")
        params.append(child_id)
    if unread_only:
        conditions.append("read=0")
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = await db.execute_fetchall(
        f"SELECT * FROM alerts {where} ORDER BY ts DESC LIMIT ?", (*params, limit)
    )
    return [{**dict(r), "read": bool(r["read"])} for r in rows]


@router.post("/{alert_id}/read", status_code=204)
async def mark_read(alert_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    await db.execute("UPDATE alerts SET read=1 WHERE id=?", (alert_id,))
    await db.commit()


@router.post("/read-all", status_code=204)
async def mark_all_read(child_id: Optional[int] = None, db=Depends(get_db), _=Depends(get_current_user)):
    if child_id is not None:
        await db.execute("UPDATE alerts SET read=1 WHERE child_id=?", (child_id,))
    else:
        await db.execute("UPDATE alerts SET read=1")
    await db.commit()


@router.get("/unread-count")
async def unread_count(db=Depends(get_db), _=Depends(get_current_user)):
    rows = await db.execute_fetchall("SELECT COUNT(*) as n FROM alerts WHERE read=0")
    return {"count": rows[0]["n"]}
