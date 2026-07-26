"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function TelegramPage() {
  const [rows, setRows] = useState<any[]>([]);
  const [chatId, setChatId] = useState("");
  const [label, setLabel] = useState("default");
  const [time, setTime] = useState("17:30");
  const [msg, setMsg] = useState("");

  useEffect(() => { load(); }, []);
  async function load() {
    try { setRows((await api.get("/telegram")).data); } catch {}
  }
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.post("/telegram", { label, chat_id: chatId, enabled: true, daily_digest_time: time });
      setMsg("Saved.");
      load();
    } catch (e: any) { setMsg("Failed: " + e.message); }
  }
  async function test(id: number) {
    const r = await api.post(`/telegram/${id}/test`);
    setMsg(r.data.message);
  }

  return (
    <div className="space-y-6 max-w-xl">
      <h1 className="text-2xl font-bold">Telegram</h1>
      <form onSubmit={submit} className="card space-y-3">
        <div><label className="text-sm text-slate-400">Label</label><input className="input" value={label} onChange={(e) => setLabel(e.target.value)} /></div>
        <div><label className="text-sm text-slate-400">Chat ID</label><input className="input" value={chatId} onChange={(e) => setChatId(e.target.value)} placeholder="123456789" required /></div>
        <div><label className="text-sm text-slate-400">Daily Digest Time</label><input className="input" value={time} onChange={(e) => setTime(e.target.value)} placeholder="17:30" /></div>
        <button className="btn" type="submit">Save</button>
        {msg && <p className="text-sm text-slate-400">{msg}</p>}
      </form>
      <div className="card">
        <h2 className="font-semibold mb-3">Settings</h2>
        {rows.map((r) => (
          <div key={r.id} className="flex justify-between items-center border-t border-slate-800 py-2 text-sm">
            <div>{r.label} — <span className="font-mono">{r.chat_id}</span> ({r.daily_digest_time})</div>
            <button className="btn-secondary text-xs" onClick={() => test(r.id)}>Test Send</button>
          </div>
        ))}
      </div>
    </div>
  );
}
