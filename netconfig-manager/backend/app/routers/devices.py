"""CRUD for network devices. Credentials are encrypted at rest with Fernet."""
from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import encrypt_secret
from ..database import get_db
from ..deps import get_current_user, require_role
from ..models import AuditLog, Device, User
from ..schemas import DeviceCreate, DeviceOut, DeviceUpdate

router = APIRouter()


@router.get("", response_model=List[DeviceOut])
async def list_devices(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
):
    result = await db.execute(select(Device).order_by(Device.name))
    return result.scalars().all()


@router.get("/{device_id}", response_model=DeviceOut)
async def get_device(
    device_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
):
    d = await db.get(Device, device_id)
    if not d:
        raise HTTPException(status_code=404, detail="Device not found")
    return d


@router.post("", response_model=DeviceOut, status_code=status.HTTP_201_CREATED)
async def create_device(
    payload: DeviceCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role("admin", "user"))],
):
    exists = await db.execute(select(Device).where(Device.name == payload.name))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Device name already exists")

    d = Device(
        name=payload.name,
        hostname=payload.hostname,
        port=payload.port,
        vendor=payload.vendor,
        description=payload.description,
        username=payload.username,
        secret_enc=encrypt_secret(payload.password),
        enable_secret_enc=encrypt_secret(payload.enable_secret) if payload.enable_secret else None,
        tags=payload.tags,
    )
    db.add(d)
    db.add(AuditLog(user_id=user.id, username=user.username, action="device_create",
                    detail={"name": payload.name, "hostname": payload.hostname}))
    await db.commit()
    await db.refresh(d)
    return d


@router.patch("/{device_id}", response_model=DeviceOut)
async def update_device(
    device_id: int,
    payload: DeviceUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role("admin", "user"))],
):
    d = await db.get(Device, device_id)
    if not d:
        raise HTTPException(status_code=404, detail="Device not found")

    if payload.name is not None: d.name = payload.name
    if payload.hostname is not None: d.hostname = payload.hostname
    if payload.port is not None: d.port = payload.port
    if payload.vendor is not None: d.vendor = payload.vendor
    if payload.description is not None: d.description = payload.description
    if payload.username is not None: d.username = payload.username
    if payload.tags is not None: d.tags = payload.tags
    if payload.password is not None: d.secret_enc = encrypt_secret(payload.password)
    if payload.enable_secret is not None:
        d.enable_secret_enc = encrypt_secret(payload.enable_secret)

    db.add(AuditLog(user_id=user.id, username=user.username, device_id=d.id, action="device_update"))
    await db.commit()
    await db.refresh(d)
    return d


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role("admin"))],
):
    d = await db.get(Device, device_id)
    if not d:
        raise HTTPException(status_code=404, detail="Device not found")
    db.add(AuditLog(user_id=user.id, username=user.username, device_id=d.id, action="device_delete"))
    await db.delete(d)
    await db.commit()
    return None
