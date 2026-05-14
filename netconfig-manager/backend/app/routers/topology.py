"""REST API for the topology / network diagram feature.

Endpoints
---------
GET    /api/topology                       → build and return full graph
PUT    /api/topology/devices/{id}/position → save (x, y) for a managed device

POST   /api/topology/nodes                 → create unmanaged object
PATCH  /api/topology/nodes/{id}            → update label / kind / position
DELETE /api/topology/nodes/{id}            → remove unmanaged object

POST   /api/topology/edges                 → create manual edge
DELETE /api/topology/edges/{id}            → remove manual edge
"""
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_user, require_role
from ..models import (
    AuditLog,
    Device,
    TopologyDevicePosition,
    TopologyEdge,
    TopologyNode,
    User,
)
from ..schemas import (
    DevicePositionUpdate,
    TopologyEdgeCreate,
    TopologyEdgeOut,
    TopologyGraph,
    TopologyNodeCreate,
    TopologyNodeOut,
    TopologyNodeUpdate,
)
from ..services.topology import build_topology, parse_endpoint

router = APIRouter()


@router.get("", response_model=TopologyGraph)
async def get_topology(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
):
    return await build_topology(db)


# ----- managed device positions -----
@router.put("/devices/{device_id}/position", status_code=status.HTTP_204_NO_CONTENT)
async def upsert_device_position(
    device_id: int,
    payload: DevicePositionUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role("admin", "user"))],
):
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    pos = await db.get(TopologyDevicePosition, device_id)
    if pos:
        pos.x = payload.x
        pos.y = payload.y
    else:
        db.add(TopologyDevicePosition(device_id=device_id, x=payload.x, y=payload.y))
    await db.commit()
    return None


# ----- unmanaged nodes -----
@router.post("/nodes", response_model=TopologyNodeOut, status_code=status.HTTP_201_CREATED)
async def create_node(
    payload: TopologyNodeCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role("admin", "user"))],
):
    n = TopologyNode(**payload.model_dump())
    db.add(n)
    db.add(AuditLog(user_id=user.id, username=user.username, action="topology_node_create",
                    detail={"label": payload.label, "kind": payload.kind}))
    await db.commit()
    await db.refresh(n)
    return n


@router.patch("/nodes/{node_id}", response_model=TopologyNodeOut)
async def update_node(
    node_id: int,
    payload: TopologyNodeUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role("admin", "user"))],
):
    n = await db.get(TopologyNode, node_id)
    if not n:
        raise HTTPException(status_code=404, detail="Node not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(n, field, value)
    await db.commit()
    await db.refresh(n)
    return n


@router.delete("/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_node(
    node_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role("admin", "user"))],
):
    n = await db.get(TopologyNode, node_id)
    if not n:
        raise HTTPException(status_code=404, detail="Node not found")
    # Also delete any manual edges that reference this node
    edges_res = await db.execute(
        select(TopologyEdge).where(
            ((TopologyEdge.source_type == "node") & (TopologyEdge.source_id == node_id))
            | ((TopologyEdge.target_type == "node") & (TopologyEdge.target_id == node_id))
        )
    )
    for e in edges_res.scalars().all():
        await db.delete(e)
    await db.delete(n)
    db.add(AuditLog(user_id=user.id, username=user.username, action="topology_node_delete",
                    detail={"id": node_id}))
    await db.commit()
    return None


# ----- manual edges -----
@router.post("/edges", response_model=TopologyEdgeOut, status_code=status.HTTP_201_CREATED)
async def create_edge(
    payload: TopologyEdgeCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role("admin", "user"))],
):
    # Validate that endpoints actually exist
    for ep_type, ep_id in (
        (payload.source_type, payload.source_id),
        (payload.target_type, payload.target_id),
    ):
        if ep_type == "device":
            if not await db.get(Device, ep_id):
                raise HTTPException(status_code=404, detail=f"device {ep_id} not found")
        else:
            if not await db.get(TopologyNode, ep_id):
                raise HTTPException(status_code=404, detail=f"node {ep_id} not found")

    e = TopologyEdge(**payload.model_dump())
    db.add(e)
    db.add(AuditLog(user_id=user.id, username=user.username, action="topology_edge_create",
                    detail={"src": f"{payload.source_type}:{payload.source_id}",
                            "dst": f"{payload.target_type}:{payload.target_id}"}))
    await db.commit()
    await db.refresh(e)
    return e


@router.delete("/edges/{edge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_edge(
    edge_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_role("admin", "user"))],
):
    e = await db.get(TopologyEdge, edge_id)
    if not e:
        raise HTTPException(status_code=404, detail="Edge not found")
    await db.delete(e)
    db.add(AuditLog(user_id=user.id, username=user.username, action="topology_edge_delete",
                    detail={"id": edge_id}))
    await db.commit()
    return None
