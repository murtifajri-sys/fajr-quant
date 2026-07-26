"use client";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { TickerLink } from "@/components/TickerLink";

const STATUSES = [
  "all",
  "IPO Early Entry",
  "IPO Mendekati Entry",
  "IPO Siap Entry",
  "IPO Watch - Akumulasi",
  "IPO Base Forming",
  "IPO Tunggu Retest",
  "IPO Data Belum Cukup",
  "IPO Risiko Tinggi",
  "IPO Hindari - Distribusi",
];

function fmtMoney(v?: number | null) {
  if (v === null || v === undefined) return "-";
  const n = Math.abs(v);
  if (n >= 1e12) return `${(v / 1e12).toFixed(1)}T`;
  if (n >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(v / 1e6).toFixed(0)}M`;
  return v.toFixed(0);
}

function fmt(v?: number | null, digits = 2) {
  if (v === null || v === undefined) return "-";
  return v.toFixed(digits);
}

function tone(status: string) {
  if (status === "IPO Early Entry" || status === "IPO Siap Entry") return "border-emerald-700/60 bg-emerald-500/10 text-emerald-300";
  if (status === "IPO Mendekati Entry") return "border-sky-700/60 bg-sky-500/10 text-sky-300";
  if (status === "IPO Tunggu Retest" || status === "IPO Base Forming") return "border-amber-700/60 bg-amber-500/10 text-amber-300";
  if (status.includes("Hindari") || status.includes("Risiko")) return "border-red-700/60 bg-red-500/10 text-red-300";
  return "border-slate-700 bg-slate-500/10 text-slate-300";
}

export default function IpoScreenerPage() {
  const [rows, setRows] = useState<any[]>([]);
  const [asOf, setAsOf] = useState("");
  const [status, setStatus] = useState("all");
  const [onlyActionable, setOnlyActionable] = useState(false);
  const [minScore, setMinScore] = useState(0);
  const [loading, setLoading] = useState(false);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [aiAnalysis, setAiAnalysis] = useState<any>(null);
  const [analysisProvider, setAnalysisProvider] = useState("");
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setMsg("");
    try {
      const params: any = { limit: 100, only_actionable: onlyActionable, min_score: minScore || undefined };
      if (status !== "all") params.status = status;
      const r = await api.get("/screener/ipo", { params });
      setRows(r.data.results || []);
      setAsOf(r.data.as_of_date || "");
    } catch (e: any) {
      setMsg(e.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  }, [minScore, onlyActionable, status]);

  useEffect(() => {
    load();
  }, [load]);

  const summary = useMemo(() => {
    const actionable = rows.filter((r) => ["IPO Early Entry", "IPO Mendekati Entry", "IPO Siap Entry"].includes(r.status)).length;
    const watch = rows.filter((r) => r.status === "IPO Watch - Akumulasi" || r.status === "IPO Base Forming").length;
    return { actionable, watch, total: rows.length };
  }, [rows]);

  async function addWatchlist(ticker: string) {
    setMsg("Saving watchlist...");
    try {
      await api.post("/watchlist", { ticker, name: "default", sort_order: 0 });
      setMsg(`${ticker} added to watchlist.`);
    } catch (e: any) {
      setMsg(e.response?.data?.detail || e.message);
    }
  }

  async function runAiAnalysis() {
    setAnalysisLoading(true);
    setMsg("");
    setAiAnalysis(null);
    try {
      const candidates = rows
        .filter((row) => !["IPO Data Belum Cukup", "IPO Hindari - Distribusi", "IPO Risiko Tinggi"].includes(row.status))
        .slice(0, 10);
      const response = await api.post("/screener/ipo/ai-analysis", { candidates, max_candidates: 10 });
      setAiAnalysis(response.data.content || {});
      setAnalysisProvider(response.data.provider || "");
      setMsg(`AI selesai menganalisis ${response.data.candidate_count || candidates.length} kandidat IPO.`);
    } catch (e: any) {
      setMsg(e.response?.data?.detail || e.message || "IPO AI analysis failed.");
    } finally {
      setAnalysisLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-bold">IPO Screener</h1>
          <p className="mt-1 text-sm text-slate-400">
            Universe maksimal 120 hari kalender sejak listing. Early entry bisa muncul mulai 6 sesi jika akumulasi dan levelnya jelas.
          </p>
        </div>
        <div className="grid grid-cols-3 gap-2 text-xs md:w-[420px]">
          <div className="rounded border border-slate-800 bg-slate-950 p-3">
            <div className="text-slate-500">Total</div>
            <div className="mt-1 text-lg font-semibold">{summary.total}</div>
          </div>
          <div className="rounded border border-slate-800 bg-slate-950 p-3">
            <div className="text-slate-500">Actionable</div>
            <div className="mt-1 text-lg font-semibold text-emerald-300">{summary.actionable}</div>
          </div>
          <div className="rounded border border-slate-800 bg-slate-950 p-3">
            <div className="text-slate-500">Watch</div>
            <div className="mt-1 text-lg font-semibold text-amber-300">{summary.watch}</div>
          </div>
        </div>
      </div>

      <div className="card flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="block text-slate-400">Status</span>
          <select className="input mt-1 w-56" value={status} onChange={(e) => setStatus(e.target.value)}>
            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <label className="text-sm">
          <span className="block text-slate-400">Min Score</span>
          <input className="input mt-1 w-28" type="number" min={0} max={100} value={minScore} onChange={(e) => setMinScore(Number(e.target.value))} />
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input type="checkbox" checked={onlyActionable} onChange={(e) => setOnlyActionable(e.target.checked)} />
          Actionable only
        </label>
        <button className="btn" onClick={load} disabled={loading}>{loading ? "Loading..." : "Apply"}</button>
        <button className="btn-secondary" onClick={runAiAnalysis} disabled={analysisLoading || rows.length === 0}>
          {analysisLoading ? "Analyzing..." : "Analisis AI"}
        </button>
        {asOf && <span className="text-xs text-slate-500">as of {asOf}</span>}
        {msg && <span className="text-xs text-slate-400">{msg}</span>}
      </div>

      {aiAnalysis && (
        <div className="rounded border border-slate-800 bg-slate-950/70 p-3 text-sm">
          <div className="mb-2 text-xs text-slate-500">Provider: {analysisProvider || "-"}</div>
          {Array.isArray(aiAnalysis.top_candidates) ? (
            <div className="space-y-2">
              {aiAnalysis.top_candidates.map((item: any, index: number) => (
                <div key={`${item.ticker || "ipo"}-${index}`} className="rounded border border-slate-800 bg-slate-900/60 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-sky-300">{item.ticker || "-"}</span>
                    <span className="rounded border border-slate-700 px-2 py-0.5 text-xs text-slate-300">{item.decision || "-"}</span>
                    <span className="text-xs text-slate-500">Priority {item.priority ?? index + 1}</span>
                  </div>
                  {item.status_reason && <p className="mt-2 text-slate-300">{item.status_reason}</p>}
                  {item.entry_plan && <p className="mt-1 text-xs text-slate-400">Plan: {item.entry_plan}</p>}
                  {item.confirmation_needed && <p className="mt-1 text-xs text-amber-200">Konfirmasi: {item.confirmation_needed}</p>}
                  {item.invalidation && <p className="mt-1 text-xs text-red-200">Invalidasi: {item.invalidation}</p>}
                  {Array.isArray(item.main_risks) && item.main_risks.length > 0 && (
                    <p className="mt-1 text-xs text-slate-400">Risiko: {item.main_risks.join(", ")}</p>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <pre className="whitespace-pre-wrap text-xs text-slate-300">{JSON.stringify(aiAnalysis, null, 2)}</pre>
          )}
          {aiAnalysis.summary && <p className="mt-3 text-slate-300">{aiAnalysis.summary}</p>}
        </div>
      )}

      <div className="overflow-x-auto rounded border border-slate-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-900 text-left text-slate-400">
              <th className="px-3 py-2">Ticker</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Age</th>
              <th className="px-3 py-2">Score</th>
              <th className="px-3 py-2">Setup</th>
              <th className="px-3 py-2">Last</th>
              <th className="px-3 py-2">Trigger</th>
              <th className="px-3 py-2">AVWAP</th>
              <th className="px-3 py-2">Flow</th>
              <th className="px-3 py-2">Value 5D</th>
              <th className="px-3 py-2">Blocker</th>
              <th className="px-3 py-2">Action</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr><td colSpan={12} className="px-3 py-8 text-center text-slate-500">No IPO candidate found</td></tr>
            ) : rows.map((row) => (
              <tr key={row.ticker} className="border-t border-slate-800 hover:bg-slate-900/40">
                <td className="px-3 py-2"><TickerLink ticker={row.ticker} /></td>
                <td className="px-3 py-2"><span className={`rounded border px-2 py-1 text-xs ${tone(row.status)}`}>{row.status}</span></td>
                <td className="px-3 py-2 font-mono text-xs">{row.calendar_age_days}d / {row.trading_session_age}s</td>
                <td className="px-3 py-2 font-mono text-xs">{fmt(row.ipo_setup_score, 1)}</td>
                <td className="px-3 py-2 font-mono text-xs">{row.setup_type}</td>
                <td className="px-3 py-2 font-mono text-xs">{fmt(row.last_price, 0)}</td>
                <td className="px-3 py-2 font-mono text-xs">{fmt(row.levels?.trigger_price, 0)}</td>
                <td className="px-3 py-2 font-mono text-xs">{fmt(row.anchored_vwap, 0)}</td>
                <td className="px-3 py-2 font-mono text-xs">
                  {row.broker_flow?.top_broker || "-"} {fmtMoney(row.broker_flow?.recent_5_net)}
                </td>
                <td className="px-3 py-2 font-mono text-xs">{fmtMoney(row.avg_value_5)}</td>
                <td className="max-w-[260px] truncate px-3 py-2 text-xs text-slate-400" title={(row.blockers || []).join(", ")}>
                  {(row.blockers || []).slice(0, 2).join(", ") || "-"}
                </td>
                <td className="px-3 py-2">
                  <div className="flex gap-2">
                    <Link className="btn-secondary text-xs" href={`/charts/${row.ticker}`}>Chart</Link>
                    <button className="btn-secondary text-xs" onClick={() => addWatchlist(row.ticker)}>Watch</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
