"""Scheduled config collector.

Compares newly-collected config against the latest stored revision (via SHA-256).
If different, persists as a new revision. If identical, only updates `collected_at`
of the most recent revision (or leaves it untouched). Audit log is written.
"""
from __future__ import annotations

import hashlib
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import decrypt_secret
from ..config import get_settings
from ..database import AsyncSessionLocal
from ..models import AuditLog, Config, Device
from .ssh_service import run_show_running_config

log = logging.getLogger("collector")
settings = get_settings()
scheduler = AsyncIOScheduler()


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()


async def collect_and_store_one(
    db: AsyncSession, device: Device, collected_by: str
) -> Config:
    """Collect one device. Returns the resulting (new or existing) Config row."""
    password = decrypt_secret(device.secret_enc)
    content = await run_show_running_config(
        host=device.hostname, port=device.port, username=device.username,
        password=password, vendor=device.vendor,
    )
    digest = _sha256(content)

    # Check latest revision
    latest_q = await db.execute(
        select(Config).where(Config.device_id == device.id).order_by(desc(Config.revision)).limit(1)
    )
    latest = latest_q.scalar_one_or_none()

    if latest and latest.content_sha256 == digest:
        log.info("device=%s unchanged (rev=%d)", device.name, latest.revision)
        return latest

    next_rev = (latest.revision + 1) if latest else 1
    new_cfg = Config(
        device_id=device.id,
        revision=next_rev,
        content=content,
        content_sha256=digest,
        collected_by=collected_by,
    )
    db.add(new_cfg)
    await db.flush()  # populate id
    log.info("device=%s new revision=%d", device.name, next_rev)
    return new_cfg


async def collect_all_job() -> None:
    """APScheduler job entrypoint."""
    log.info("scheduled collection start")
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Device))
        devices = result.scalars().all()
        for d in devices:
            try:
                cfg = await collect_and_store_one(db, d, collected_by="scheduler")
                db.add(AuditLog(device_id=d.id, action="config_collect_scheduled",
                                detail={"revision": cfg.revision}))
            except Exception as e:
                log.exception("device=%s collection failed", d.name)
                db.add(AuditLog(device_id=d.id, action="config_collect_failed",
                                detail={"error": str(e)}))
        await db.commit()
    log.info("scheduled collection done")


async def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(
        collect_all_job,
        "interval",
        minutes=settings.collect_interval_minutes,
        id="collect_all",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    log.info("scheduler started (interval=%dm)", settings.collect_interval_minutes)


async def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
