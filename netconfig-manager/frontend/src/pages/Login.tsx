import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";

export default function Login() {
  const [username, setU] = useState("");
  const [password, setP] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const nav = useNavigate();

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    try {
      const form = new URLSearchParams();
      form.set("username", username);
      form.set("password", password);
      // OAuth2 password flow expects x-www-form-urlencoded
      const res = await axios.post("/api/auth/login", form, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });
      localStorage.setItem("token", res.data.access_token);
      nav("/devices");
    } catch (e: any) {
      setErr(e.response?.data?.detail ?? "ログインに失敗しました");
    }
  };

  return (
    <main style={{ maxWidth: 400 }}>
      <h2>NetConfig Manager ログイン</h2>
      <form onSubmit={onSubmit} className="card" style={{ display: "grid", gap: ".75rem" }}>
        <label>ユーザ名 <input value={username} onChange={e => setU(e.target.value)} required /></label>
        <label>パスワード <input type="password" value={password} onChange={e => setP(e.target.value)} required /></label>
        {err && <div style={{ color: "crimson" }}>{err}</div>}
        <button type="submit" className="primary">ログイン</button>
      </form>
    </main>
  );
}
