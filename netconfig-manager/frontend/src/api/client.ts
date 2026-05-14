import axios from "axios";

export const api = axios.create({
  baseURL: "/api",
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("token");
      if (location.pathname !== "/login") location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export type UserOut = {
  id: number;
  username: string;
  email?: string | null;
  role: "admin" | "user" | "readonly";
  is_active: boolean;
  created_at: string;
};

export type DeviceOut = {
  id: number;
  name: string;
  hostname: string;
  port: number;
  vendor: string;
  description?: string | null;
  username: string;
  tags: string[];
  created_at: string;
};

export type ConfigOut = {
  id: number;
  device_id: number;
  revision: number;
  content_sha256: string;
  collected_at: string;
  collected_by: string;
  note?: string | null;
};

// ----- Topology -----
export type NodeKind = "cloud" | "router" | "switch" | "firewall" | "server" | "generic";
export type EndpointType = "device" | "node";

export type TopologyInterface = {
  name: string;
  description?: string | null;
  ip?: string | null;
  enabled: boolean;
};

export type TopologyGraphNode = {
  id: string;
  label: string;
  kind: string;
  is_managed: boolean;
  x: number;
  y: number;
  detail: {
    hostname?: string;
    vendor?: string;
    interfaces?: TopologyInterface[];
    note?: string;
  };
};

export type TopologyGraphEdge = {
  id: string;
  source: string;
  target: string;
  source_iface?: string | null;
  target_iface?: string | null;
  auto_detected: boolean;
  confidence: "confirmed" | "one_way";
  note?: string | null;
};

export type TopologyGraph = {
  nodes: TopologyGraphNode[];
  edges: TopologyGraphEdge[];
};

export type TopologyNodeOut = {
  id: number;
  label: string;
  kind: NodeKind;
  x: number;
  y: number;
  note?: string | null;
};

export type TopologyEdgeOut = {
  id: number;
  source_type: EndpointType;
  source_id: number;
  source_iface?: string | null;
  target_type: EndpointType;
  target_id: number;
  target_iface?: string | null;
  note?: string | null;
};
