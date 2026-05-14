"""FastAPI entrypoint."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import auth as auth_router
from .routers import configs as configs_router
from .routers import devices as devices_router
from .routers import terminal as terminal_router
from .routers import topology as topology_router
from .routers import users as users_router
from .services.collector import scheduler, start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("netconfig")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting NetConfig Manager backend")
    await start_scheduler()
    try:
        yield
    finally:
        log.info("Shutting down")
        await stop_scheduler()


app = FastAPI(title="NetConfig Manager", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST
app.include_router(auth_router.router, prefix="/api/auth", tags=["auth"])
app.include_router(users_router.router, prefix="/api/users", tags=["users"])
app.include_router(devices_router.router, prefix="/api/devices", tags=["devices"])
app.include_router(configs_router.router, prefix="/api/configs", tags=["configs"])
app.include_router(topology_router.router, prefix="/api/topology", tags=["topology"])

# WebSocket (terminal)
app.include_router(terminal_router.router, prefix="/ws", tags=["terminal"])


@app.get("/api/healthz")
async def healthz():
    return {"status": "ok", "scheduler": scheduler.running}
