"""Endpoints for generating and downloading device agent artifacts."""
import sys
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

# Make agents directory importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from db.database import get_db
from auth import get_current_user

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("/{child_id}/ios-profile")
async def download_ios_profile(
    child_id: int,
    disable_vpn: bool = True,
    disable_hotspot: bool = False,
    disable_airdrop: bool = False,
    db=Depends(get_db),
    _=Depends(get_current_user),
):
    """Generate and download a .mobileconfig for the given child."""
    rows = await db.execute_fetchall("SELECT * FROM children WHERE id=?", (child_id,))
    if not rows:
        raise HTTPException(404, "Child not found")
    child = dict(rows[0])

    settings = await db.execute_fetchall("SELECT value FROM settings WHERE key='guardhome_ip'")
    guardhome_ip = settings[0]["value"] if settings else None
    dns_servers = [guardhome_ip] if guardhome_ip else None

    from agents.ios.profile_generator.generator import generate_profile, profile_filename
    plist_bytes = generate_profile(
        child_name=child["name"],
        disable_vpn_install=disable_vpn,
        disable_hotspot=disable_hotspot,
        disable_airdrop=disable_airdrop,
        dns_servers=dns_servers,
    )

    filename = profile_filename(child["name"])
    return Response(
        content=plist_bytes,
        media_type="application/x-apple-aspen-config",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
