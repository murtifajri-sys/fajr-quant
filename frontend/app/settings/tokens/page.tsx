"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function TokensPage() {
  const [tokens, setTokens] = useState<any[]>([]);
  const [label, setLabel] = useState("default");
  const [token, setToken] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [msg, setMsg] = useState("");

  async function load() {
    try {
      const r = await api.get("/tokens");
      setTokens(r.data);
    } catch (e: any) {
      setMsg("Failed to load tokens: " + e.message);
    }
  }

  useEffect(() => { load(); }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setMsg("Saving...");
    try {
      await api.post("/tokens", { label, token, expires_at: expiresAt || null });
      setToken("");
      setMsg("Token saved.");
      load();
    } catch (e: any) {
      setMsg("Failed: " + e.message);
    }
  }

  async function activate(id: number) {
    await api.post(`/tokens/${id}/activate`);
    load();
  }

  async function remove(id: number) {
    await api.delete(`/tokens/${id}`);
    load();
  }

  async function test(id: number) {
    setMsg("Testing Stockbit connection...");
    try {
      const response = await api.post(`/tokens/${id}/test`);
      setMsg(response.data.message);
    } catch (e: any) {
      setMsg(e.response?.data?.detail || e.message);
    }
    load();
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold">Stockbit Token</h1>
      <form onSubmit={submit} className="card space-y-3">
        <div>
          <label className="text-sm text-slate-400">Label</label>
          <input className="input" value={label} onChange={(e) => setLabel(e.target.value)} />
        </div>
        <div>
          <label className="text-sm text-slate-400">Bearer Token (JWT)</label>
          <textarea
            className="input font-mono text-xs"
            rows={5}
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="eyJhbGciOi..."
            required
          />
        </div>
        <div>
          <label className="text-sm text-slate-400">Expires At (optional)</label>
          <input type="datetime-local" className="input" value={expiresAt} onChange={(e) => setExpiresAt(e.target.value)} />
        </div>
        <button className="btn" type="submit">Save Token</button>
        {msg && <p className="text-sm text-slate-400">{msg}</p>}
      </form>

      <div className="card">
        <h2 className="font-semibold mb-3">Stored Tokens</h2>
        {tokens.length === 0 ? (
          <p className="text-slate-400 text-sm">No tokens yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead><tr className="text-slate-400"><th className="text-left">Label</th><th>Status</th><th>Expires</th><th>Error</th><th></th></tr></thead>
            <tbody>
              {tokens.map((t) => (
                <tr key={t.id} className="border-t border-slate-800">
                  <td className="py-1">
                    {t.label}
                    {t.warning && <div className="text-amber-400 text-xs mt-0.5">⚠ {t.warning}</div>}
                  </td>
                  <td className={`text-center ${t.is_expired || t.status === "error" ? "text-red-400" : "text-emerald-400"}`}>{t.status}</td>
                  <td className="text-center text-xs">{t.expires_at?.slice(0, 16) ?? "-"}</td>
                  <td className="text-xs text-red-300 max-w-48 truncate">{t.last_error ?? "-"}</td>
                  <td className="text-right space-x-2">
                    {!t.active && <button className="btn-secondary text-xs" onClick={() => activate(t.id)}>Activate</button>}
                    <button className="btn-secondary text-xs" onClick={() => test(t.id)}>Test</button>
                    <button className="btn-secondary text-xs" onClick={() => remove(t.id)}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
