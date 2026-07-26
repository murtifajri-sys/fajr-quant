"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { TickerLink } from "@/components/TickerLink";

export default function WatchlistPage() {
  const [items, setItems] = useState<any[]>([]);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [ticker, setTicker] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);

  async function load() {
    try {
      const r = await api.get("/watchlist");
      setItems(r.data);
    } catch (e: any) {
      setMsg(`Failed to load watchlist: ${e.message}`);
    }
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const r = await api.get("/stocks", { params: { q: query, limit: 10 } });
        setResults(r.data);
      } catch {
        setResults([]);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [query]);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!ticker.trim()) return;
    setLoading(true);
    setMsg("Saving...");
    try {
      await api.post("/watchlist", { ticker: ticker.trim().toUpperCase(), name: "default", sort_order: items.length });
      setTicker("");
      setQuery("");
      setResults([]);
      setMsg("Ticker added to watchlist.");
      await load();
    } catch (e: any) {
      setMsg(e.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  }

  async function remove(id: number) {
    setLoading(true);
    try {
      await api.delete(`/watchlist/${id}`);
      setMsg("Ticker removed.");
      await load();
    } catch (e: any) {
      setMsg(e.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold">Watchlist</h1>
        <p className="mt-1 text-sm text-slate-400">
          Ticker di sini bisa dipakai sebagai universe `watchlist` di screener dan pipeline terkait.
        </p>
      </div>

      <form onSubmit={add} className="card space-y-3">
        <div>
          <label className="text-sm text-slate-400">Cari saham</label>
          <input
            className="input"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setTicker(e.target.value.toUpperCase());
            }}
            placeholder="Ketik ticker atau nama saham"
          />
        </div>
        {results.length > 0 && (
          <div className="rounded border border-slate-800 bg-slate-950/60">
            {results.map((row) => (
              <button
                key={row.ticker}
                type="button"
                className="flex w-full items-center justify-between border-t border-slate-800 px-3 py-2 text-left first:border-t-0 hover:bg-slate-900"
                onClick={() => {
                  setTicker(row.ticker);
                  setQuery(`${row.ticker} - ${row.name || ""}`);
                  setResults([]);
                }}
              >
                <span className="font-mono text-sky-300">{row.ticker}</span>
                <span className="text-sm text-slate-400">{row.name}</span>
              </button>
            ))}
          </div>
        )}
        <div>
          <label className="text-sm text-slate-400">Ticker terpilih</label>
          <input className="input font-mono" value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} placeholder="BBCA" />
        </div>
        <button className="btn" type="submit" disabled={loading || !ticker.trim()}>
          {loading ? "Saving..." : "Add to Watchlist"}
        </button>
        {msg && <p className="text-sm text-slate-400">{msg}</p>}
      </form>

      <div className="card">
        <h2 className="mb-3 font-semibold">Current Watchlist</h2>
        {items.length === 0 ? (
          <p className="text-sm text-slate-400">Watchlist masih kosong.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-slate-400">
                <th className="text-left">Ticker</th>
                <th className="text-left">Chart</th>
                <th className="text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="border-t border-slate-800">
                  <td className="py-2"><TickerLink ticker={item.ticker} /></td>
                  <td className="py-2">
                    <a href={`/charts/${item.ticker}`} className="text-sm text-sky-300 underline-offset-4 hover:underline">
                      Open chart
                    </a>
                  </td>
                  <td className="text-right">
                    <button className="btn-secondary text-xs" onClick={() => remove(item.id)} disabled={loading}>
                      Remove
                    </button>
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
