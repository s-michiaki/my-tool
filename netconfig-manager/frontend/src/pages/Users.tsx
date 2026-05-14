import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, UserOut } from "../api/client";

export default function Users({ me }: { me: UserOut }) {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["users"],
    queryFn: () => api.get<UserOut[]>("/users").then(r => r.data),
  });

  const [form, setForm] = useState({ username: "", password: "", email: "", role: "user" as const });
  const create = useMutation({
    mutationFn: (f: typeof form) => api.post("/users", f),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["users"] });
                       setForm({ username: "", password: "", email: "", role: "user" }); },
  });

  const del = useMutation({
    mutationFn: (id: number) => api.delete(`/users/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  return (
    <>
      <h2>ユーザ管理</h2>

      <form className="card" style={{ display: "grid", gap: ".5rem", gridTemplateColumns: "repeat(4, 1fr)", marginBottom: "1rem" }}
            onSubmit={e => { e.preventDefault(); create.mutate(form); }}>
        <input placeholder="username" value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} required />
        <input placeholder="email"    value={form.email}    onChange={e => setForm({ ...form, email: e.target.value })} />
        <input placeholder="password (≥8)" type="password" minLength={8}
               value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} required />
        <select value={form.role} onChange={e => setForm({ ...form, role: e.target.value as any })}>
          <option value="admin">admin</option>
          <option value="user">user</option>
          <option value="readonly">readonly</option>
        </select>
        <button type="submit" className="primary" style={{ gridColumn: "1 / span 4" }}>追加</button>
      </form>

      <table>
        <thead><tr><th>username</th><th>email</th><th>role</th><th>有効</th><th></th></tr></thead>
        <tbody>
          {(data ?? []).map(u => (
            <tr key={u.id}>
              <td>{u.username}</td>
              <td>{u.email}</td>
              <td>{u.role}</td>
              <td>{u.is_active ? "○" : "×"}</td>
              <td>
                <button onClick={() => del.mutate(u.id)} disabled={u.id === me.id}>削除</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
