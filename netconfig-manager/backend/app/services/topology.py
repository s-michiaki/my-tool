"""Build a topology graph from collected configs + user-placed objects.

Algorithm
---------
1. Load every managed device (with its latest stored config revision).
2. Parse each config into a list of `ParsedInterface`.
3. For each interface description, search for any *other* device's name
   (case-insensitive substring match). If found, record a candidate link
   `A.if -> B`.
4. Pair candidate links into edges:
     - if both `A.if -> B` AND `B.if' -> A` exist → confidence='confirmed'
     - if only one direction exists → confidence='one_way'
5. Merge in manual edges (`topology_edges`) and unmanaged nodes
   (`topology_nodes`) verbatim.
6. Attach saved positions from `topology_device_positions` (defaulting to
   an auto-layout if the device has no saved coordinates).

The output uses string IDs of the form `device:<id>` and `node:<id>` so the
frontend can resolve endpoint types uniformly.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Config, Device, TopologyDevicePosition, TopologyEdge, TopologyNode
from ..schemas import TopologyGraph, TopologyGraphEdge, TopologyGraphNode
from .config_parser import ParsedInterface, parse_config


def _device_aliases(d: Device) -> list[str]:
    """Possible names that may appear in another device's description."""
    aliases = {d.name}
    # hostname without domain
    host = (d.hostname or "").split(".")[0]
    if host:
        aliases.add(host)
    return [a for a in aliases if a]


def _find_referenced_device(
    description: str, devices: list[Device], self_id: int
) -> Device | None:
    """Return the most likely referenced device given an interface description."""
    if not description:
        return None
    text = description.lower()
    # Prefer longest alias to avoid 'sw' matching 'sw01' first.
    candidates: list[tuple[int, Device]] = []
    for d in devices:
        if d.id == self_id:
            continue
        for alias in _device_aliases(d):
            if not alias:
                continue
            if re.search(r"\b" + re.escape(alias.lower()) + r"\b", text):
                candidates.append((len(alias), d))
                break
    if not candidates:
        return None
    candidates.sort(key=lambda t: -t[0])
    return candidates[0][1]


def _auto_layout(index: int, total: int) -> tuple[float, float]:
    """Default circular layout for devices without saved positions."""
    if total <= 1:
        return (0.0, 0.0)
    radius = 60 + total * 25
    angle = (2 * math.pi * index) / total
    return (radius * math.cos(angle), radius * math.sin(angle))


@dataclass
class _Candidate:
    src_device_id: int
    src_iface: str
    dst_device_id: int

    def key(self) -> tuple[int, int]:
        return (self.src_device_id, self.dst_device_id)


async def build_topology(db: AsyncSession) -> TopologyGraph:
    # 1) Load all devices
    devices_res = await db.execute(select(Device).order_by(Device.id))
    devices: list[Device] = list(devices_res.scalars().all())

    # 2) Load latest config per device
    latest_configs: dict[int, Config] = {}
    for d in devices:
        r = await db.execute(
            select(Config)
            .where(Config.device_id == d.id)
            .order_by(desc(Config.revision))
            .limit(1)
        )
        c = r.scalar_one_or_none()
        if c:
            latest_configs[d.id] = c

    # 3) Parse each config
    parsed_per_device: dict[int, list[ParsedInterface]] = {}
    for d in devices:
        cfg = latest_configs.get(d.id)
        if not cfg:
            parsed_per_device[d.id] = []
            continue
        parsed_per_device[d.id] = parse_config(d.vendor, cfg.content)

    # 4) Build candidate links from descriptions
    candidates: list[_Candidate] = []
    for d in devices:
        for iface in parsed_per_device.get(d.id, []):
            if not iface.description:
                continue
            target = _find_referenced_device(iface.description, devices, d.id)
            if target:
                candidates.append(
                    _Candidate(
                        src_device_id=d.id,
                        src_iface=iface.name,
                        dst_device_id=target.id,
                    )
                )

    # 5) Pair them up: confirmed if both directions exist
    by_src: dict[tuple[int, int], _Candidate] = {c.key(): c for c in candidates}
    auto_edges: list[TopologyGraphEdge] = []
    seen_pairs: set[tuple[int, int]] = set()
    for c in candidates:
        pair = tuple(sorted([c.src_device_id, c.dst_device_id]))
        if pair in seen_pairs:
            continue
        reverse = by_src.get((c.dst_device_id, c.src_device_id))
        confidence = "confirmed" if reverse else "one_way"
        seen_pairs.add(pair)
        # canonical edge: smaller-id side as source
        if c.src_device_id < c.dst_device_id:
            src_id, src_if, dst_id, dst_if = (
                c.src_device_id,
                c.src_iface,
                c.dst_device_id,
                reverse.src_iface if reverse else None,
            )
        else:
            src_id, src_if, dst_id, dst_if = (
                c.dst_device_id,
                reverse.src_iface if reverse else None,
                c.src_device_id,
                c.src_iface,
            )
        eid = "auto:" + hashlib.sha1(
            f"{src_id}-{src_if}-{dst_id}-{dst_if}".encode()
        ).hexdigest()[:12]
        auto_edges.append(
            TopologyGraphEdge(
                id=eid,
                source=f"device:{src_id}",
                target=f"device:{dst_id}",
                source_iface=src_if,
                target_iface=dst_if,
                auto_detected=True,
                confidence=confidence,
            )
        )

    # 6) Load manual edges and unmanaged nodes
    manual_res = await db.execute(select(TopologyEdge))
    manual_edges_rows = list(manual_res.scalars().all())
    manual_edges = [
        TopologyGraphEdge(
            id=f"manual:{e.id}",
            source=f"{e.source_type}:{e.source_id}",
            target=f"{e.target_type}:{e.target_id}",
            source_iface=e.source_iface,
            target_iface=e.target_iface,
            auto_detected=False,
            confidence="confirmed",
            note=e.note,
        )
        for e in manual_edges_rows
    ]

    unmanaged_res = await db.execute(select(TopologyNode))
    unmanaged = list(unmanaged_res.scalars().all())

    # 7) Load saved positions
    pos_res = await db.execute(select(TopologyDevicePosition))
    positions = {p.device_id: (p.x, p.y) for p in pos_res.scalars().all()}

    # 8) Build the unified node list
    nodes: list[TopologyGraphNode] = []
    for i, d in enumerate(devices):
        x, y = positions.get(d.id, _auto_layout(i, max(len(devices), 1)))
        iface_summary = [
            {
                "name": iface.name,
                "description": iface.description,
                "ip": iface.ip,
                "enabled": iface.enabled,
            }
            for iface in parsed_per_device.get(d.id, [])
        ]
        nodes.append(
            TopologyGraphNode(
                id=f"device:{d.id}",
                label=d.name,
                kind=d.vendor,
                is_managed=True,
                x=float(x),
                y=float(y),
                detail={
                    "hostname": d.hostname,
                    "vendor": d.vendor,
                    "interfaces": iface_summary,
                },
            )
        )

    for n in unmanaged:
        nodes.append(
            TopologyGraphNode(
                id=f"node:{n.id}",
                label=n.label,
                kind=n.kind,
                is_managed=False,
                x=float(n.x),
                y=float(n.y),
                detail={"note": n.note} if n.note else {},
            )
        )

    return TopologyGraph(nodes=nodes, edges=auto_edges + manual_edges)


def parse_endpoint(s: str) -> tuple[str, int]:
    """Parse 'device:42' or 'node:7' → ('device', 42)."""
    try:
        kind, id_str = s.split(":", 1)
        return kind, int(id_str)
    except (ValueError, AttributeError):
        raise ValueError(f"invalid endpoint: {s!r}")
