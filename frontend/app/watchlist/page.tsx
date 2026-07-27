"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { TickerLink } from "@/components/TickerLink";
import { normalizeTradeSetup, setupReasonText, setupTargetText } from "@/lib/tradeSetup";
import { evaluateTradeStatus } from "@/lib/tradeStatus";

export default function WatchlistPage() {
  const [items, setItems] = useState<any[]>([]);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [ticker, setTicker] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisMsg, setAnalysisMsg] = useState("");
  const [analysisErr, setAnalysisErr] = useState("");
  const [analysisProvider, setAnalysisProvider] = useState("");
  const [analysisCandidates, setAnalysisCandidates] = useState<any[]>([]);
  const [aiAnalysis, setAiAnalysis] = useState<any>(null);

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

  async function runWatchlistAiAnalysis() {
    setAnalysisLoading(true);
    setAnalysisErr("");
    setAnalysisMsg("");
    setAnalysisProvider("");
    setAnalysisCandidates([]);
    setAiAnalysis(null);
    try {
      const screenerResponse = await fetch("/api/screener/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
        body: JSON.stringify({
          methods: [],
          bandar_labels: [],
          phases: [],
          min_composite: 0,
          require_foreign_inflow: false,
          breakout_filter: false,
          universe: "watchlist",
          top_n: Math.max(10, items.length || 10),
          require_broker_accumulation: true,
          broker_period_days: 30,
          min_broker_net_pct_mcap: 0.05,
          min_broker_net_pct_adv: 0.5,
          min_broker_active_days: 3,
          min_broker_positive_ratio: 0.5,
          min_broker_coverage_ratio: 0.8,
          max_broker_balance_ratio: 0.05,
          min_broker_conviction_score: 55,
          min_entry_readiness_score: 45,
          exclude_stale: false,
          exclude_reversal_risk: true,
          exclude_insufficient_data: true,
          require_recent: false,
          require_acceleration: false,
          require_cluster_confirmation: false,
          sort_by: "combined_rank",
          broker_rank_weight: 0.7,
          entry_rank_weight: 0.3,
          broker_score_config: { accumulation_min_score: 55 },
        }),
      });
      const screenerPayload = await screenerResponse.json();
      if (!screenerResponse.ok) {
        throw new Error(screenerPayload?.detail || screenerPayload?.message || "Failed to run watchlist screener.");
      }

      const rows = (screenerPayload.results || []).map((row: any) => {
        const broker = row.dominant_factors?.broker_accumulation || {};
        const tradeStatus = evaluateTradeStatus({
          broker_conviction: {
            score: row.broker_conviction_score,
            label: row.broker_conviction_label,
            status: row.broker_status,
            config: broker?.score_config,
          },
          flow_quality: {
            score: row.flow_quality_score,
            label: row.flow_quality_label,
            retail_distribution_risk: broker?.retail_distribution_risk,
            high_freq_low_value: broker?.high_freq_low_value,
            low_freq_high_value: broker?.low_freq_high_value,
          },
          entry_readiness: {
            score: row.entry_readiness_score,
            phase: row.phase,
            tags: [],
          },
          one_month: broker,
        });
        const setup = normalizeTradeSetup(row, broker);
        return { row, broker, tradeStatus, setup };
      });
      setAnalysisCandidates(rows);

      const candidates = rows.slice(0, 10).map(({ row, broker, tradeStatus, setup }: any) => ({
        rank: row.rank,
        ticker: row.ticker,
        name: row.name,
        composite: row.composite,
        phase: row.phase,
        broker_conviction_score: row.broker_conviction_score,
        broker_conviction_label: row.broker_conviction_label,
        flow_quality_score: row.flow_quality_score,
        flow_quality_label: row.flow_quality_label,
        entry_readiness_score: row.entry_readiness_score,
        combined_rank_score: row.combined_rank_score,
        trade_status: tradeStatus,
        setup_detail: setup,
        broker,
      }));
      if (candidates.length === 0) {
        setAnalysisMsg("Tidak ada kandidat watchlist yang lolos data broker/screener untuk dianalisis.");
        return;
      }

      const analysisResponse = await fetch("/api/screener/trade-candidates-analysis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
        body: JSON.stringify({ candidates, max_candidates: 10 }),
      });
      const analysisPayload = await analysisResponse.json();
      if (!analysisResponse.ok) {
        throw new Error(analysisPayload?.detail || analysisPayload?.message || "AI analysis failed.");
      }
      setAiAnalysis(analysisPayload.content || {});
      setAnalysisProvider(analysisPayload.provider || "");
      setAnalysisMsg(`AI selesai menganalisis ${analysisPayload.candidate_count || candidates.length} ticker watchlist.`);
    } catch (e: any) {
      setAnalysisErr(e.message || "AI analysis failed.");
    } finally {
      setAnalysisLoading(false);
    }
  }

  return (
    <div className="space-y-6">
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
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-semibold">Current Watchlist</h2>
          <button className="btn text-xs" onClick={runWatchlistAiAnalysis} disabled={analysisLoading || items.length === 0}>
            {analysisLoading ? "Analyzing..." : "Analisis AI Watchlist"}
          </button>
        </div>
        <div className="mb-3 space-y-2">
          <p className="text-xs text-slate-500">
            Analisis memakai hasil screener universe watchlist, maksimal 10 ticker dengan data broker/setup yang tersedia.
          </p>
          {analysisErr && <p className="text-xs text-red-400">{analysisErr}</p>}
          {analysisMsg && <p className="text-xs text-emerald-300">{analysisMsg}</p>}
          {aiAnalysis && (
            <div className="rounded border border-slate-800 bg-slate-950/70 p-3 text-sm">
              <div className="mb-2 text-xs text-slate-500">Provider: {analysisProvider || "-"}</div>
              {Array.isArray(aiAnalysis.top_candidates) ? (
                <div className="space-y-2">
                  {aiAnalysis.top_candidates.map((item: any, index: number) => (
                    <div key={`${item.ticker || "candidate"}-${index}`} className="rounded border border-slate-800 bg-slate-900/60 p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-sky-300">{item.ticker || "-"}</span>
                        <span className="rounded border border-slate-700 px-2 py-0.5 text-xs text-slate-300">{item.decision || "-"}</span>
                        <span className="text-xs text-slate-500">Priority {item.priority ?? index + 1}</span>
                      </div>
                      {(item.setup_label || item.trigger_or_zone || item.invalidation) && (
                        <div className="mt-2 grid gap-2 text-xs text-slate-400 md:grid-cols-3">
                          <div><span className="text-slate-500">Setup</span> {item.setup_label || "-"}</div>
                          <div><span className="text-slate-500">Target</span> {item.trigger_or_zone || "-"}</div>
                          <div><span className="text-slate-500">Invalidasi</span> {item.invalidation || "-"}</div>
                        </div>
                      )}
                      {item.reason && <p className="mt-2 text-slate-300">{item.reason}</p>}
                      {item.confirmation_needed && <p className="mt-1 text-xs text-amber-200">Konfirmasi: {item.confirmation_needed}</p>}
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
          {analysisCandidates.length > 0 && (
            <div className="overflow-x-auto rounded border border-slate-800">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-slate-950/70 text-slate-400">
                    <th className="px-2 py-2 text-left">Ticker</th>
                    <th className="px-2 py-2">Trade</th>
                    <th className="px-2 py-2">Setup</th>
                    <th className="px-2 py-2">Target</th>
                    <th className="px-2 py-2">Jarak</th>
                    <th className="px-2 py-2">Conv</th>
                    <th className="px-2 py-2">Flow</th>
                    <th className="px-2 py-2">Entry</th>
                  </tr>
                </thead>
                <tbody>
                  {analysisCandidates.map(({ row, tradeStatus, setup }: any) => (
                    <tr key={row.ticker} className="border-t border-slate-800">
                      <td className="px-2 py-2"><TickerLink ticker={row.ticker} /></td>
                      <td className="px-2 py-2 text-center">{tradeStatus.label}</td>
                      <td className="px-2 py-2 text-center">
                        <div>{setup.label || "-"}</div>
                        <div className="text-[11px] text-slate-500">{setupReasonText(setup.blockers?.[0] || setup.confirmations?.[0])}</div>
                      </td>
                      <td className="px-2 py-2 text-center font-mono text-amber-200">{setupTargetText(setup)}</td>
                      <td className="px-2 py-2 text-center font-mono">{setup.distance_pct !== null && setup.distance_pct !== undefined ? `${setup.distance_pct.toFixed(2)}%` : "-"}</td>
                      <td className="px-2 py-2 text-center font-mono text-amber-300">{row.broker_conviction_score?.toFixed(1) ?? "-"}</td>
                      <td className="px-2 py-2 text-center font-mono text-cyan-300">{row.flow_quality_score?.toFixed(1) ?? "-"}</td>
                      <td className="px-2 py-2 text-center font-mono text-sky-300">{row.entry_readiness_score?.toFixed(1) ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
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
