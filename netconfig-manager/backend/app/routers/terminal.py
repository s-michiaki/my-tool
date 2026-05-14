"""WebSocket-based SSH terminal proxy.

Browser <-(WebSocket)-> backend <-(AsyncSSH PTY)-> device

Frames:
  - Browser -> backend
      {"type":"input","data":"ls\\n"}
      {"type":"resize","cols":120,"rows":40}
  - backend -> browser
      {"type":"data","data":"..."}
      {"type":"closed","code":0,"reason":"..."}
"""
import asyncio
import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import decrypt_secret
from ..database import get_db
from ..deps import ws_authenticate
from ..models import AuditLog, Device, User
from ..services.ssh_service import open_interactive

log = logging.getLogger("terminal")
router = APIRouter()


@router.websocket("/terminal/{device_id}")
async def terminal_ws(
    websocket: WebSocket,
    device_id: int,
    user: Annotated[User, Depends(ws_authenticate)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    device = await db.get(Device, device_id)
    if not device:
        await websocket.close(code=4404, reason="Device not found")
        return

    await websocket.accept()
    log.info("terminal open user=%s device=%s", user.username, device.name)

    db.add(AuditLog(user_id=user.id, username=user.username, device_id=device.id,
                    action="ssh_open", detail={"hostname": device.hostname}))
    await db.commit()

    password = decrypt_secret(device.secret_enc)

    try:
        async with open_interactive(
            host=device.hostname,
            port=device.port,
            username=device.username,
            password=password,
        ) as (process, ssh_conn):

            async def from_browser():
                while True:
                    raw = await websocket.receive_text()
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    mtype = msg.get("type")
                    if mtype == "input":
                        data = msg.get("data", "")
                        process.stdin.write(data)
                    elif mtype == "resize":
                        try:
                            process.change_terminal_size(int(msg["cols"]), int(msg["rows"]))
                        except Exception:
                            pass

            async def to_browser():
                while not process.stdout.at_eof():
                    chunk = await process.stdout.read(4096)
                    if not chunk:
                        break
                    await websocket.send_text(json.dumps({"type": "data", "data": chunk}))

            done, pending = await asyncio.wait(
                {asyncio.create_task(from_browser()), asyncio.create_task(to_browser())},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()

    except WebSocketDisconnect:
        log.info("ws disconnect")
    except Exception as e:
        log.exception("terminal error")
        try:
            await websocket.send_text(json.dumps({"type": "closed", "reason": str(e)}))
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
        db.add(AuditLog(user_id=user.id, username=user.username, device_id=device.id,
                        action="ssh_close"))
        await db.commit()
