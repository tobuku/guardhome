import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm

from db.database import init_db
from auth import verify_password, create_access_token, get_current_user
from db.database import get_db
from routers import children, devices, rules, reports, alerts, setup


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Start background scheduler (log sync, schedule enforcement, birthday checks)
    from scheduler import start_scheduler
    scheduler = start_scheduler()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="GuardHome API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production if desired
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(children.router)
app.include_router(devices.router)
app.include_router(rules.router)
app.include_router(reports.router)
app.include_router(alerts.router)
app.include_router(setup.router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.post("/api/auth/login")
async def login(form: OAuth2PasswordRequestForm = Depends(), db=Depends(get_db)):
    rows = await db.execute_fetchall("SELECT value FROM settings WHERE key='password_hash'")
    if not rows:
        raise HTTPException(400, "Password not set — complete setup first.")
    stored_hash = rows[0]["value"]
    if not verify_password(form.password, stored_hash):
        raise HTTPException(401, "Incorrect password")
    token = create_access_token({"sub": "parent"})
    return {"access_token": token, "token_type": "bearer"}


@app.post("/api/auth/change-password")
async def change_password(old_password: str, new_password: str, db=Depends(get_db), _=Depends(get_current_user)):
    rows = await db.execute_fetchall("SELECT value FROM settings WHERE key='password_hash'")
    if not rows or not verify_password(old_password, rows[0]["value"]):
        raise HTTPException(401, "Current password incorrect")
    from auth import hash_password
    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('password_hash', ?)",
        (hash_password(new_password),),
    )
    await db.commit()
    return {"ok": True}
