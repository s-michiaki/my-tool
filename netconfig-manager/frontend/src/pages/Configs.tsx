import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { useState } from "react";
import { api, ConfigOut } from "../api/client";

export default function Configs() {
  const { id } = useParams();
  const deviceId = Number(id);
  const { data: list } = useQuery({
    queryKey: ["configs", deviceId],
    queryFn: () => api.get<ConfigOut[]>(`/configs/devices/${deviceId}`).then(r => r.data),
    refetchInterval: 30_000,
  });

  const [sel, setSel] = useState<number | null>(null);
  const [from, setFrom] = useState<number | null>(null);
  const [to, setTo] = useState<number | null>(null);

  const { data: detail } = useQuery({
    queryKey: ["config-detail", sel],
    queryFn: () => api.get(`/configs/${sel}`).then(r => r.data as ConfigOut & { content: string }),
    enabled: !!sel,
  });

  const { data: diff } = useQuery({
    queryKey: ["diff", deviceId, from, to],
    queryFn: () => api.get(`/configs/devices/${deviceId}/diff`, { params: { from_rev: from, to_rev: to } })
      .then(r => r.data as { diff: string }),
    enabled: !!from && !!to,
  });

  return (
    <>
      <h2>コンフィグ世代 (device #{deviceId})</h2>
      <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: "1rem" }}>
        <table>
          <thead><tr><th>rev</th><th>収集</th><th>by</th><th></th></tr></thead>
          <tbody>
            {(list ?? []).map(c => (
              <tr key={c.id} style={{ background: sel === c.id ? "#dbeafe" : undefined }}>
                <td>{c.revision}</td>
                <td>{new Date(c.collected_at).toLocaleString()}</td>
                <td>{c.collected_by}</td>
                <td style={{ display: "flex", gap: 4 }}>
                  <button onClick={() => setSel(c.id)}>表示</button>
                  <button onClick={() => setFrom(c.revision)}>← from</button>
                  <button onClick={() => setTo(c.revision)}>to →</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div>
          {detail && (
            <>
              <h3>rev {detail.revision} ({detail.content_sha256.slice(0, 12)}…)</h3>
              <pre className="diff" style={{ maxHeight: 600 }}>{detail.content}</pre>
            </>
          )}
          {from && to && diff && (
            <>
              <h3>diff: rev{from} → rev{to}</h3>
              <pre className="diff" style={{ maxHeight: 600 }}>
                {diff.diff.split("\n").map((line, i) => (
                  <span key={i} className={line.startsWith("+") ? "add" : line.startsWith("-") ? "del" : ""}>
                    {line}{"\n"}
                  </span>
                ))}
              </pre>
            </>
          )}
        </div>
      </div>
    </>
  );
}
