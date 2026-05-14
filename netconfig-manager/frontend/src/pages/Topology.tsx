import { useCallback, useEffect, useMemo, useState } from "react";
import ReactFlow, {
  addEdge,
  Background,
  Connection,
  Controls,
  Edge,
  EdgeChange,
  MarkerType,
  MiniMap,
  Node,
  NodeChange,
  ReactFlowProvider,
  applyEdgeChanges,
  applyNodeChanges,
} from "reactflow";
import "reactflow/dist/style.css";
import { api, NodeKind, TopologyGraph, TopologyGraphNode } from "../api/client";

/**
 * Topology editor.
 *
 *  - Managed devices: rendered as blue rectangles. Auto-detected links
 *    (from interface descriptions) are drawn as edges (dashed = one_way,
 *    solid = confirmed both directions).
 *  - Unmanaged objects: user-placed shapes (cloud / router / switch /
 *    firewall / server / generic). Drag from palette to add.
 *  - Edges can be dragged between any two nodes to create manual links.
 *  - Drag a node to move it; the position is persisted on drop.
 */

const KIND_ICONS: Record<NodeKind, string> = {
  cloud: "☁",
  router: "⇆",
  switch: "▦",
  firewall: "🛡",
  server: "▤",
  generic: "◇",
};

const KIND_COLORS: Record<NodeKind, string> = {
  cloud: "#dbeafe",
  router: "#fef3c7",
  switch: "#dcfce7",
  firewall: "#fee2e2",
  server: "#ede9fe",
  generic: "#f1f5f9",
};

function toRfNode(n: TopologyGraphNode): Node {
  const isUnmanaged = !n.is_managed;
  const kind = (n.kind as NodeKind) || "generic";
  return {
    id: n.id,
    position: { x: n.x, y: n.y },
    data: { label: n.label, raw: n },
    type: "default",
    style: {
      background: isUnmanaged ? KIND_COLORS[kind] ?? "#f1f5f9" : "#1e3a8a",
      color: isUnmanaged ? "#0f172a" : "#fff",
      border: isUnmanaged ? "1px dashed #64748b" : "1px solid #1e3a8a",
      borderRadius: 6,
      padding: 8,
      fontSize: 12,
      width: 160,
    },
  };
}

function edgeStyle(e: { auto_detected: boolean; confidence: string }) {
  if (!e.auto_detected) return { stroke: "#0f172a", strokeWidth: 2 };
  if (e.confidence === "confirmed") return { stroke: "#10b981", strokeWidth: 2 };
  return { stroke: "#f59e0b", strokeWidth: 1.5, strokeDasharray: "5 4" };
}

function TopologyInner() {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [selected, setSelected] = useState<TopologyGraphNode | null>(null);
  const [loading, setLoading] = useState(true);

  const loadGraph = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get<TopologyGraph>("/topology");
      setNodes(r.data.nodes.map(toRfNode));
      setEdges(
        r.data.edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          label:
            (e.source_iface || e.target_iface)
              ? `${e.source_iface ?? "?"} ↔ ${e.target_iface ?? "?"}`
              : undefined,
          style: edgeStyle(e),
          markerEnd: { type: MarkerType.ArrowClosed },
          data: e,
        })),
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadGraph();
  }, [loadGraph]);

  // ----- node interactions
  const onNodesChange = useCallback(
    (changes: NodeChange[]) => setNodes((nds) => applyNodeChanges(changes, nds)),
    [],
  );

  const onNodeDragStop = useCallback(async (_: unknown, node: Node) => {
    // Persist position
    const [kind, idStr] = node.id.split(":");
    const id = Number(idStr);
    try {
      if (kind === "device") {
        await api.put(`/topology/devices/${id}/position`, {
          x: node.position.x,
          y: node.position.y,
        });
      } else {
        await api.patch(`/topology/nodes/${id}`, {
          x: node.position.x,
          y: node.position.y,
        });
      }
    } catch (e) {
      console.error("position save failed", e);
    }
  }, []);

  // ----- edge interactions
  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => setEdges((eds) => applyEdgeChanges(changes, eds)),
    [],
  );

  const onConnect = useCallback(
    async (conn: Connection) => {
      if (!conn.source || !conn.target) return;
      const [stype, sid] = conn.source.split(":");
      const [ttype, tid] = conn.target.split(":");
      try {
        const r = await api.post("/topology/edges", {
          source_type: stype,
          source_id: Number(sid),
          target_type: ttype,
          target_id: Number(tid),
        });
        const eid = `manual:${r.data.id}`;
        setEdges((eds) =>
          addEdge(
            {
              ...conn,
              id: eid,
              style: edgeStyle({ auto_detected: false, confidence: "confirmed" }),
              markerEnd: { type: MarkerType.ArrowClosed },
              data: { auto_detected: false },
            } as Edge,
            eds,
          ),
        );
      } catch (e) {
        console.error("edge create failed", e);
      }
    },
    [],
  );

  const onEdgeDelete = useCallback(async (edge: Edge) => {
    // Only manual edges are deletable (auto edges regenerate from configs)
    if (!edge.id.startsWith("manual:")) {
      alert("自動検出されたエッジは削除できません (description 元を編集してください)");
      return;
    }
    const id = Number(edge.id.split(":")[1]);
    try {
      await api.delete(`/topology/edges/${id}`);
      setEdges((eds) => eds.filter((e) => e.id !== edge.id));
    } catch (e) {
      console.error(e);
    }
  }, []);

  const onNodeClick = useCallback((_: unknown, node: Node) => {
    setSelected(node.data?.raw ?? null);
  }, []);

  // ----- palette: add unmanaged objects
  const addUnmanaged = useCallback(async (kind: NodeKind) => {
    const label = prompt(`${kind} の名前`, kind);
    if (!label) return;
    try {
      const r = await api.post("/topology/nodes", {
        label, kind, x: 0, y: 0,
      });
      const fresh: TopologyGraphNode = {
        id: `node:${r.data.id}`,
        label: r.data.label,
        kind: r.data.kind,
        is_managed: false,
        x: r.data.x,
        y: r.data.y,
        detail: { note: r.data.note },
      };
      setNodes((nds) => [...nds, toRfNode(fresh)]);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const deleteUnmanaged = useCallback(async () => {
    if (!selected || selected.is_managed) return;
    if (!confirm(`${selected.label} を削除しますか?`)) return;
    const id = Number(selected.id.split(":")[1]);
    try {
      await api.delete(`/topology/nodes/${id}`);
      setNodes((nds) => nds.filter((n) => n.id !== selected.id));
      setEdges((eds) => eds.filter((e) => e.source !== selected.id && e.target !== selected.id));
      setSelected(null);
    } catch (e) {
      console.error(e);
    }
  }, [selected]);

  const kinds: NodeKind[] = ["cloud", "router", "switch", "firewall", "server", "generic"];

  const detail = useMemo(() => {
    if (!selected) return null;
    return (
      <div className="card" style={{ position: "absolute", right: 16, top: 16, width: 320, maxHeight: "70vh", overflow: "auto" }}>
        <h3 style={{ margin: "0 0 .5rem" }}>
          {selected.label}{" "}
          <small style={{ color: "#64748b" }}>
            ({selected.is_managed ? "managed" : "unmanaged"})
          </small>
        </h3>
        {selected.detail?.hostname && (
          <div style={{ fontSize: 13 }}>
            host: <code>{selected.detail.hostname}</code>
          </div>
        )}
        {selected.detail?.vendor && (
          <div style={{ fontSize: 13 }}>vendor: {selected.detail.vendor}</div>
        )}
        {selected.detail?.note && (
          <div style={{ fontSize: 13, marginTop: 4 }}>note: {selected.detail.note}</div>
        )}
        {selected.detail?.interfaces && selected.detail.interfaces.length > 0 && (
          <>
            <h4 style={{ margin: "0.75rem 0 .25rem" }}>Interfaces</h4>
            <table>
              <thead><tr><th>name</th><th>desc</th><th>ip</th></tr></thead>
              <tbody>
                {selected.detail.interfaces.map((i) => (
                  <tr key={i.name} style={{ color: i.enabled ? undefined : "#94a3b8" }}>
                    <td>{i.name}</td>
                    <td>{i.description}</td>
                    <td>{i.ip}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
        {!selected.is_managed && (
          <button onClick={deleteUnmanaged} style={{ marginTop: 8 }}>
            この管理外オブジェクトを削除
          </button>
        )}
      </div>
    );
  }, [selected, deleteUnmanaged]);

  return (
    <>
      <h2>
        構成図{" "}
        <button onClick={loadGraph}>{loading ? "..." : "↻ 再構築"}</button>
      </h2>
      <div className="card" style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
        <span style={{ fontWeight: 600 }}>管理外を追加:</span>
        {kinds.map((k) => (
          <button key={k} onClick={() => addUnmanaged(k)} title={k}>
            {KIND_ICONS[k]} {k}
          </button>
        ))}
        <span style={{ marginLeft: 16, color: "#64748b", fontSize: 12 }}>
          凡例:{" "}
          <span style={{ color: "#10b981" }}>━ 両端確認</span>{" "}
          <span style={{ color: "#f59e0b" }}>--- 片側のみ</span>{" "}
          <span style={{ color: "#0f172a" }}>━ 手動追加</span>
        </span>
      </div>
      <div style={{ height: "75vh", border: "1px solid #cbd5e1", position: "relative" }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeDragStop={onNodeDragStop}
          onNodeClick={onNodeClick}
          onEdgeDoubleClick={(_, edge) => onEdgeDelete(edge)}
          fitView
        >
          <MiniMap pannable zoomable />
          <Controls />
          <Background gap={16} />
        </ReactFlow>
        {detail}
      </div>
      <div style={{ marginTop: 8, fontSize: 12, color: "#64748b" }}>
        ノードをドラッグで配置 / ノード右の点を引っ張って手動接続 / エッジをダブルクリックで削除 (手動分のみ)
      </div>
    </>
  );
}

export default function Topology() {
  return (
    <ReactFlowProvider>
      <TopologyInner />
    </ReactFlowProvider>
  );
}
