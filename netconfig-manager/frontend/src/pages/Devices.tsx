import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useState } from "react";
import { api, DeviceOut } from "../api/client";
import Topology from "./Topology";

const VENDORS = ["cisco_ios", "cisco_xe", "cisco_nxos", "arista_eos", "juniper_junos", "linux"];

type DeviceForm = {
  name: string; hostname: string; port: number; vendor: string;
  username: string; password: string; description?: string;
};

type Tab = "list" | "topology";

function DeviceList() {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["devices"],
    queryFn: () => api.get<DeviceOut[]>("/devices").then(r => r.data),
  });

  const [show, setShow] = useState(false);
  const [form, setForm] = useState<DeviceForm>({
    name: "", hostname: "", port: 22, vendor: "cisco_ios", username: "", password: "",
  });

  const create = useMutation({
    mutationFn: (f: DeviceForm) => api.post("/devices", f),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["devices"] });
      setShow(false);
      setForm({ name: "", hostname: "", port: 22, vendor: "cisco_ios", username: "", password: "" });
    },
  });

  const collect = useMutation({
    mutationFn: (id: number) => api.post(`/configs/devices/${id}/collect`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["configs"] }),
  });

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <h3 style={{ margin: 0 }}>機器一覧</h3>
        <button onClick={() => setShow(s => !s)}>{show ? "閉じる" : "+ 追加"}</button>
      </div>

      {show && (
        <form className="card" style={{ display: "grid", gap: ".5rem", marginTop: ".75rem", marginBottom: "1rem", gridTemplateColumns: "1fr 1fr" }}
              onSubmit={(e) => { e.preventDefault(); create.mutate(form); }}>
          <label>名称 <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required /></label>
          <label>ホスト <input value={form.hostname} onChange={e => setForm({ ...form, hostname: e.target.value })} required /></label>
          <label>ポート <input type="number" value={form.port} onChange={e => setForm({ ...form, port: +e.target.value })} /></label>
          <label>ベンダ
            <select value={form.vendor} onChange={e => setForm({ ...form, vendor: e.target.value })}>
              {VENDORS.map(v => <option key={v}>{v}</option>)}
            </select>
          </label>
          <label>ユーザ <input value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} required /></label>
          <label>パスワード <input type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} required /></label>
          <label style={{ gridColumn: "1 / span 2" }}>説明
            <input value={form.description ?? ""} onChange={e => setForm({ ...form, description: e.target.value })} />
          </label>
          <button type="submit" className="primary" style={{ gridColumn: "1 / span 2" }}>登録</button>
        </form>
      )}

      <table style={{ marginTop: ".75rem" }}>
        <thead><tr><th>名称</th><th>ホスト</th><th>ベンダ</th><th>操作</th></tr></thead>
        <tbody>
          {(data ?? []).map(d => (
            <tr key={d.id}>
              <td>{d.name}</td>
              <td>{d.hostname}:{d.port}</td>
              <td>{d.vendor}</td>
              <td style={{ display: "flex", gap: ".5rem" }}>
                <button onClick={() => collect.mutate(d.id)}
                        disabled={collect.isPending}>コンフィグ収集</button>
                <Link to={`/devices/${d.id}/configs`}><button>世代</button></Link>
                <Link to={`/devices/${d.id}/terminal`}><button>SSH</button></Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

export default function Devices() {
  // Persist tab choice in localStorage so reloading keeps the user's view.
  const [tab, setTab] = useState<Tab>(
    () => (localStorage.getItem("devicesTab") as Tab) || "list",
  );
  const switchTab = (t: Tab) => {
    setTab(t);
    localStorage.setItem("devicesTab", t);
  };

  const tabBtn = (id: Tab, label: string) => (
    <button
      onClick={() => switchTab(id)}
      style={{
        padding: "0.5rem 1rem",
        background: tab === id ? "#2563eb" : "#f1f5f9",
        color: tab === id ? "#fff" : "#0f172a",
        border: "1px solid " + (tab === id ? "#1d4ed8" : "#cbd5e1"),
        borderBottom: tab === id ? "1px solid #2563eb" : "1px solid #cbd5e1",
        borderRadius: "6px 6px 0 0",
        cursor: "pointer",
        marginRight: 4,
      }}
    >
      {label}
    </button>
  );

  return (
    <>
      <h2>機器</h2>
      <div style={{ borderBottom: "1px solid #cbd5e1", marginBottom: "1rem" }}>
        {tabBtn("list", "一覧")}
        {tabBtn("topology", "構成図")}
      </div>

      {tab === "list" && <DeviceList />}
      {tab === "topology" && <Topology />}
    </>
  );
}
