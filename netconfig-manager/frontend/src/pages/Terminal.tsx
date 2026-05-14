import { useEffect, useRef } from "react";
import { useParams } from "react-router-dom";
import { Terminal as XTerm } from "xterm";
import { FitAddon } from "xterm-addon-fit";

export default function TerminalPage() {
  const { id } = useParams();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const token = localStorage.getItem("token") ?? "";
    const term = new XTerm({
      cursorBlink: true,
      fontFamily: "Menlo, Consolas, monospace",
      fontSize: 14,
      theme: { background: "#0b1021" },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(ref.current);
    fit.fit();

    const wsProto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${wsProto}://${location.host}/ws/terminal/${id}?token=${encodeURIComponent(token)}`);

    ws.onopen = () => {
      term.writeln("\x1b[32m[connected]\x1b[0m");
      ws.send(JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }));
    };
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === "data") term.write(msg.data);
        else if (msg.type === "closed") term.writeln(`\r\n\x1b[31m[closed]\x1b[0m ${msg.reason ?? ""}`);
      } catch { /* ignore */ }
    };
    ws.onclose = () => term.writeln("\r\n\x1b[31m[disconnected]\x1b[0m");
    ws.onerror = () => term.writeln("\r\n\x1b[31m[ws error]\x1b[0m");

    term.onData((d) => ws.send(JSON.stringify({ type: "input", data: d })));

    const onResize = () => {
      fit.fit();
      if (ws.readyState === 1) {
        ws.send(JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }));
      }
    };
    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("resize", onResize);
      ws.close();
      term.dispose();
    };
  }, [id]);

  return (
    <>
      <h2>ターミナル (device #{id})</h2>
      <div ref={ref} style={{ height: "70vh", background: "#0b1021", padding: 8 }} />
    </>
  );
}
