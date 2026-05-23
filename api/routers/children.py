from fastapi import APIRouter, Depends, HTTPException
from typing import List
import json

from db.database import get_db
from models.schemas import ChildCreate, ChildUpdate, ChildOut
from auth import get_current_user

router = APIRouter(prefix="/api/children", tags=["children"])

# Default category rules per preset
PRESET_RULES = {
    "elementary": {
        "adult": True, "violence": True, "gore": True, "gore_anime": True,
        "gambling": True, "drugs": True, "social_media": True, "gaming": False,
        "streaming": False, "political_extremism": True, "self_harm": True,
        "chat_apps": True, "vpn": True,
    },
    "middle_school": {
        "adult": True, "violence": True, "gore": True, "gore_anime": True,
        "gambling": True, "drugs": True, "social_media": False, "gaming": False,
        "streaming": False, "political_extremism": True, "self_harm": True,
        "chat_apps": False, "vpn": True,
    },
    "high_school": {
        "adult": True, "violence": False, "gore": True, "gore_anime": True,
        "gambling": True, "drugs": False, "social_media": False, "gaming": False,
        "streaming": False, "political_extremism": False, "self_harm": True,
        "chat_apps": False, "vpn": False,
    },
    "custom": {},
}


@router.get("", response_model=List[ChildOut])
async def list_children(db=Depends(get_db), _=Depends(get_current_user)):
    rows = await db.execute_fetchall("SELECT * FROM children ORDER BY name")
    return [dict(r) for r in rows]


@router.post("", response_model=ChildOut, status_code=201)
async def create_child(body: ChildCreate, db=Depends(get_db), _=Depends(get_current_user)):
    cursor = await db.execute(
        "INSERT INTO children (name, age, birthday, preset, avatar) VALUES (?,?,?,?,?)",
        (body.name, body.age, body.birthday, body.preset, body.avatar),
    )
    await db.commit()
    child_id = cursor.lastrowid

    # Apply preset category rules
    rules = PRESET_RULES.get(body.preset, PRESET_RULES["middle_school"])
    for category, blocked in rules.items():
        await db.execute(
            "INSERT OR REPLACE INTO category_rules (child_id, category, blocked) VALUES (?,?,?)",
            (child_id, category, int(blocked)),
        )
    await db.commit()

    row = await db.execute_fetchall("SELECT * FROM children WHERE id=?", (child_id,))
    return dict(row[0])


@router.get("/{child_id}", response_model=ChildOut)
async def get_child(child_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    rows = await db.execute_fetchall("SELECT * FROM children WHERE id=?", (child_id,))
    if not rows:
        raise HTTPException(404, "Child not found")
    return dict(rows[0])


@router.patch("/{child_id}", response_model=ChildOut)
async def update_child(child_id: int, body: ChildUpdate, db=Depends(get_db), _=Depends(get_current_user)):
    rows = await db.execute_fetchall("SELECT * FROM children WHERE id=?", (child_id,))
    if not rows:
        raise HTTPException(404, "Child not found")

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        set_clause = ", ".join(f"{k}=?" for k in updates)
        await db.execute(f"UPDATE children SET {set_clause} WHERE id=?", (*updates.values(), child_id))
        await db.commit()

    # Re-apply preset if changed
    if body.preset and body.preset in PRESET_RULES:
        rules = PRESET_RULES[body.preset]
        for category, blocked in rules.items():
            await db.execute(
                "INSERT OR REPLACE INTO category_rules (child_id, category, blocked) VALUES (?,?,?)",
                (child_id, category, int(blocked)),
            )
        await db.commit()

    rows = await db.execute_fetchall("SELECT * FROM children WHERE id=?", (child_id,))
    return dict(rows[0])


@router.delete("/{child_id}", status_code=204)
async def delete_child(child_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    await db.execute("DELETE FROM children WHERE id=?", (child_id,))
    await db.commit()


@router.get("/{child_id}/categories")
async def get_child_categories(child_id: int, db=Depends(get_db), _=Depends(get_current_user)):
    rows = await db.execute_fetchall(
        "SELECT category, blocked FROM category_rules WHERE child_id=?", (child_id,)
    )
    return {r["category"]: bool(r["blocked"]) for r in rows}


@router.put("/{child_id}/categories")
async def set_child_category(child_id: int, category: str, blocked: bool, db=Depends(get_db), _=Depends(get_current_user)):
    await db.execute(
        "INSERT OR REPLACE INTO category_rules (child_id, category, blocked) VALUES (?,?,?)",
        (child_id, category, int(blocked)),
    )
    await db.commit()

    # Sync to AdGuard
    from core.filter_manager import sync_child_rules
    await sync_child_rules(child_id, db)

    await db.execute(
        "INSERT INTO audit_log (action, detail) VALUES (?,?)",
        ("category_toggle", f"child={child_id} category={category} blocked={blocked}"),
    )
    await db.commit()
    return {"ok": True}
