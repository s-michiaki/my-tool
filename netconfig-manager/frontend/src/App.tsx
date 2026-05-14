import { Navigate, Route, Routes, Link, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import Login from "./pages/Login";
import Devices from "./pages/Devices";
import Configs from "./pages/Configs";
import Terminal from "./pages/Terminal";
import Users from "./pages/Users";
import { api, UserOut } from "./api/client";

function Layout({ children, me }: { children: React.ReactNode; me: UserOut }) {
  const nav = useNavigate();
  const logout = () => { localStorage.removeItem("token"); nav("/login"); };
  return (
    <>
      <nav>
        <Link to="/devices">機器</Link>
        {me.role === "admin" && <Link to="/users">ユーザ</Link>}
        <span style={{ marginLeft: "auto" }}>
          {me.username} ({me.role}) <button onClick={logout}>ログアウト</button>
        </span>
      </nav>
      <main>{children}</main>
    </>
  );
}

function Authed({ children }: { children: (me: UserOut) => React.ReactNode }) {
  const [me, setMe] = useState<UserOut | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!localStorage.getItem("token")) { setLoading(false); return; }
    api.get<UserOut>("/users/me")
      .then(r => setMe(r.data))
      .catch(() => setMe(null))
      .finally(() => setLoading(false));
  }, []);
  if (loading) return <main>Loading...</main>;
  if (!me) return <Navigate to="/login" replace />;
  return <Layout me={me}>{children(me)}</Layout>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/devices" element={<Authed>{() => <Devices />}</Authed>} />
      <Route path="/devices/:id/configs" element={<Authed>{() => <Configs />}</Authed>} />
      <Route path="/devices/:id/terminal" element={<Authed>{() => <Terminal />}</Authed>} />
      <Route path="/users" element={<Authed>{(me) => <Users me={me} />}</Authed>} />
      <Route path="*" element={<Navigate to="/devices" />} />
    </Routes>
  );
}
