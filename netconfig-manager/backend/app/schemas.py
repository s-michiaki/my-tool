from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


# ----- Auth -----
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


# ----- Users -----
class UserBase(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    email: Optional[EmailStr] = None
    role: Literal["admin", "user", "readonly"] = "user"
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=256)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    role: Optional[Literal["admin", "user", "readonly"]] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8, max_length=256)


class UserOut(UserBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ----- Devices -----
class DeviceBase(BaseModel):
    name: str
    hostname: str
    port: int = 22
    vendor: str   # cisco_ios, cisco_xe, juniper_junos, arista_eos, linux ...
    description: Optional[str] = None
    username: str
    tags: list[str] = Field(default_factory=list)


class DeviceCreate(DeviceBase):
    password: str
    enable_secret: Optional[str] = None


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    hostname: Optional[str] = None
    port: Optional[int] = None
    vendor: Optional[str] = None
    description: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    enable_secret: Optional[str] = None
    tags: Optional[list[str]] = None


class DeviceOut(DeviceBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ----- Configs -----
class ConfigOut(BaseModel):
    id: int
    device_id: int
    revision: int
    content_sha256: str
    collected_at: datetime
    collected_by: str
    note: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class ConfigDetail(ConfigOut):
    content: str


class ConfigDiff(BaseModel):
    from_revision: int
    to_revision: int
    diff: str


# ----- Topology -----
NodeKind = Literal["cloud", "router", "switch", "firewall", "server", "generic"]
EndpointType = Literal["device", "node"]


class TopologyNodeBase(BaseModel):
    label: str = Field(..., min_length=1, max_length=128)
    kind: NodeKind = "generic"
    x: float = 0.0
    y: float = 0.0
    note: Optional[str] = None


class TopologyNodeCreate(TopologyNodeBase):
    pass


class TopologyNodeUpdate(BaseModel):
    label: Optional[str] = None
    kind: Optional[NodeKind] = None
    x: Optional[float] = None
    y: Optional[float] = None
    note: Optional[str] = None


class TopologyNodeOut(TopologyNodeBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class DevicePositionUpdate(BaseModel):
    x: float
    y: float


class TopologyEdgeBase(BaseModel):
    source_type: EndpointType
    source_id: int
    source_iface: Optional[str] = None
    target_type: EndpointType
    target_id: int
    target_iface: Optional[str] = None
    note: Optional[str] = None


class TopologyEdgeCreate(TopologyEdgeBase):
    pass


class TopologyEdgeOut(TopologyEdgeBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class TopologyGraphNode(BaseModel):
    """Unified node representation returned by GET /api/topology."""
    id: str                  # "device:<id>" or "node:<id>"
    label: str
    kind: str                # device vendor or topology_node kind
    is_managed: bool
    x: float
    y: float
    detail: dict = Field(default_factory=dict)   # interfaces, hostname, etc.


class TopologyGraphEdge(BaseModel):
    id: str                  # "auto:<hash>" or "manual:<id>"
    source: str              # endpoint id (e.g. "device:1")
    target: str
    source_iface: Optional[str] = None
    target_iface: Optional[str] = None
    auto_detected: bool
    confidence: str          # 'confirmed' | 'one_way'
    note: Optional[str] = None


class TopologyGraph(BaseModel):
    nodes: list[TopologyGraphNode]
    edges: list[TopologyGraphEdge]
