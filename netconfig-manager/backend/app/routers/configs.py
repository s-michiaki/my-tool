"""Config collection and versioning."""
import difflib
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_user, require_role
from ..models import AuditLog, Config, Device, User
from ..schemas import ConfigDetail, ConfigDiff, ConfigOut
from ..services.collector import collect_and_store_one

router = APIRouter()


@router.get("/devices/{device_id}", response_model=List[ConfigOut])
async def list_configs(
    device_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
):
    result = await db.execute(
        select(Config).where(Config.device_id == device_id).order_by(Config.revision.desc())
    )
    return result.scalars().all()


@router.get("/{config_id}", response_model=ConfigDetail)
async def get_config(
    config_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
):
    c = await db.get(Config, config_id)
    if not c:
        raise HTTPException(status_code=404, detail="Config not found")
    return c


@router.get("/devices/{device_id}/diff", response_model=ConfigDiff)
async def diff_configs(
    device_id: int,
    from_rev: int,
    to_rev: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
):
    res = await db.execute(
        select(Config).where(Config.device_id == device_id, Config.revision.in_([from_rev, to_rev]))
    )
    rows = {c.revision: c for c in res.scalars().all()}
    if from_rev not in rows or to_rev not in rows:
        raise HTTPException(status_code=404, detail="Revision not found")

    a = rows[from_rev].content.splitlines(keepends=True)
    b = rows[to_rev].content.splitlines(keepends=True)
    diff = "".join(
        difflib.unified_diff(a, b, fromfile=f"rev{from_rev}", tofile=f"rev{to_rev}", lineterm="")
    )
    return ConfigDiff(from_revision=from_rev, to_revision=to_rev, diff=diff)


@router.post("/devices/{device_id}/collect", response_model=ConfigOut)
async def collect_now(
    device_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role("admin", "user"))],
):
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    try:
        new_config = await collect_and_store_one(db, device, collected_by=user.username)
    except Exception as e:
        db.add(AuditLog(user_id=user.id, username=user.username, device_id=device.id,
                        action="config_collect_failed", detail={"error": str(e)}))
        await db.commit()
        raise HTTPException(status_code=502, detail=f"Collection failed: {e}")

    db.add(AuditLog(user_id=user.id, username=user.username, device_id=device.id,
                    action="config_collect",
                    detail={"revision": new_config.revision, "changed": True}))
    await db.commit()
    return new_config
