"""Setup wizard endpoints — unauthenticated until password is set."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from db.database import get_db
from auth import hash_password, create_access_token
from routers.children import PRESET_RULES

router = APIRouter(prefix="/api/setup", tags=["setup"])


class SetupPasswordRequest(BaseModel):
    password: str


class WizardChildEntry(BaseModel):
    name: str
    age: int
    birthday: Optional[str] = None
    preset: str = "middle_school"


@router.get("/status")
async def setup_status(db=Depends(get_db)):
    """Returns wizard completion state. Public endpoint used by dashboard to decide first-run flow."""
    settings = {
        r["key"]: r["value"]
        for r in await db.execute_fetchall("SELECT key, value FROM settings")
    }
    children_count = (await db.execute_fetchall("SELECT COUNT(*) as n FROM children"))[0]["n"]
    devices_assigned = (await db.execute_fetchall(
        "SELECT COUNT(*) as n FROM devices WHERE child_id IS NOT NULL"
    ))[0]["n"]

    return {
        "wizard_complete": settings.get("wizard_complete") == "1",
        "password_set": settings.get("password_hash") is not None,
        "network_name": settings.get("network_name", ""),
        "children_count": children_count,
        "devices_assigned": devices_assigned,
    }


@router.post("/password")
async def set_password(body: SetupPasswordRequest, db=Depends(get_db)):
    """Set the parent dashboard password. Only works if no password is set yet."""
    existing = await db.execute_fetchall("SELECT value FROM settings WHERE key='password_hash'")
    if existing:
        raise HTTPException(400, "Password already set. Use /api/auth/change-password.")
    hashed = hash_password(body.password)
    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('password_hash', ?)", (hashed,)
    )
    await db.commit()
    token = create_access_token({"sub": "parent"})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/network")
async def set_network_name(network_name: str, db=Depends(get_db)):
    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('network_name', ?)",
        (network_name,),
    )
    await db.commit()
    return {"ok": True}


@router.post("/children/bulk")
async def bulk_add_children(children: List[WizardChildEntry], db=Depends(get_db)):
    """Add multiple children in one call during wizard step 2."""
    created = []
    for c in children:
        cursor = await db.execute(
            "INSERT INTO children (name, age, birthday, preset) VALUES (?,?,?,?)",
            (c.name, c.age, c.birthday, c.preset),
        )
        child_id = cursor.lastrowid
        rules = PRESET_RULES.get(c.preset, PRESET_RULES["middle_school"])
        for category, blocked in rules.items():
            await db.execute(
                "INSERT OR REPLACE INTO category_rules (child_id, category, blocked) VALUES (?,?,?)",
                (child_id, category, int(blocked)),
            )
        created.append({"id": child_id, "name": c.name})
    await db.commit()
    return {"created": created}


@router.post("/complete")
async def complete_wizard(db=Depends(get_db)):
    """Mark wizard as done. Triggers initial AdGuard sync."""
    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('wizard_complete', '1')"
    )
    await db.commit()

    # Push all child rules to AdGuard
    from core.filter_manager import sync_all_rules
    await sync_all_rules(db)

    return {"ok": True}
