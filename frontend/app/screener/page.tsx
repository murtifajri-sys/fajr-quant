"use client";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";
import { DataTable } from "@/components/DataTable";
import { TickerLink } from "@/components/TickerLink";
import { normalizeTradeSetup, setupMatchesFilter, setupReasonText, setupTargetText, setupTone, type SetupFilter } from "@/lib/tradeSetup";
import { evaluateTradeStatus } from "@/lib/tradeStatus";

const METHODS = ["trend_structure","price_action","volume_breakout","harmonic","relative_strength","candlestick","elliott_wave"];
const BANDAR = ["hidden_accumulation","silent_accumulation","shakeout","absorption","bandar_positioning","consistency"];
const PHASES = ["Awal","Tunggu Konfirmasi","Siap Entry","Hold","Siap Jual","Exit"];
const TRADE_STATUS_FILTERS = [
  ["all", "All Trade"],
  ["ready", "Siap Entry"],
  ["waiting", "Tunggu Konfirmasi"],
  ["hold", "Hold"],
  ["unavailable", "Data Belum Siap"],
] as const;
const SETUP_FILTERS: ReadonlyArray<[SetupFilter, string]> = [
  ["all", "All Setup"],
  ["ready", "Siap Entry"],
  ["wait_breakout", "Breakout"],
  ["wait_retest", "Retest"],
  ["buy_on_weakness", "BOW"],
  ["wait_value_area", "Value Area"],
  ["no_setup", "Hold"],
];
const BROKER_LABELS = ["accumulation", "big_accumulation", "aggressive_accumulation"];
const SORT_OPTIONS = [
  ["combined_rank", "Combined Rank"],
  ["broker_conviction", "Broker Conviction"],
  ["entry_readiness", "Entry Readiness"],
  ["composite", "Composite"],
] as const;

const COLUMN_HINTS: Record<string, string> = {
  conviction: "Skor 0-100 yang merangkum magnitude, persistence, recency, acceleration, retention, cluster, purity, dan quality broker flow.",
  entry: "Skor 0-100 untuk kesiapan entry harga saat ini, terpisah dari conviction broker.",
  combined: "Default rank = broker conviction x bobot broker + entry readiness x bobot entry.",
  flow: "Flow quality memisahkan pola smart-like vs retail-like. Fokusnya pada ukuran per trade, consistency freq, retention, dan cluster support.",
  status: "Status engine broker: active, stale, reversal_risk, insufficient_data, atau no_accumulation.",
  label: "Label akhir conviction broker setelah gate coverage, recency, persistence, cluster, dan penalty lolos.",
  broker: "Broker utama adalah top net buyer. Cluster menampilkan top-3 buyer sebagai konfirmasi akumulasi.",
  net: "Net buy broker utama selama periode terpilih.",
  mcap: "Net broker utama sebagai persentase market cap saham.",
  adv: "Days ADV = net broker utama dibagi average daily traded value. Angka 2.0 berarti setara dua hari nilai transaksi normal.",
  pos: "Positive days / trading days untuk broker utama, dipakai sebagai ukuran persistence.",
  lastBuy: "Tanggal sesi terakhir broker utama tercatat net buy.",
  warnings: "Peringatan cepat untuk coverage rendah, stale, reversal, atau broker flow yang tidak lagi recent.",
  closest: "Ranking kandidat non-smart yang paling dekat ke smart-like accumulation berdasarkan flow quality, retention, cluster support, dan penalty retail-noise.",
  trade: "Status gabungan untuk entry baru. Menggabungkan broker conviction, flow quality, entry readiness, recency, cluster, dan risk flags.",
  setup: "Titik tunggu deterministik: breakout, retest, BOW, value area, atau no setup. AI memakai angka ini sebagai sumber level.",
  distance: "Jarak harga terakhir ke trigger atau zona setup. Negatif berarti area tunggu berada di bawah harga sekarang.",
  techPhase: "Fase teknikal dari scoring harga. Ini belum tentu layak entry bila broker flow quality tidak mendukung.",
};

interface BacktestReturnSummary {
  count: number;
  avg_return_pct?: number | null;
  median_return_pct?: number | null;
  win_rate?: number | null;
}

interface BrokerBacktestSample {
  ticker: string;
  date: string;
  label: string;
  score?: number | null;
  status?: string | null;
  liquidity_bucket: string;
  forward_returns_pct: Record<string, number | null>;
}

interface BrokerBacktestPayload {
  as_of_date?: string | null;
  period_days: number;
  lookback_days: number;
  universe: string;
  horizons: number[];
  summary_by_label: Record<string, Record<string, BacktestReturnSummary>>;
  summary_by_label_and_liquidity: Record<string, Record<string, Record<string, BacktestReturnSummary>>>;
  samples: BrokerBacktestSample[];
}

function fmtMoney(v: number) {
  const n = Math.abs(v);
  if (n >= 1e12) return `${(v / 1e12).toFixed(1)}T`;
  if (n >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(v / 1e6).toFixed(0)}M`;
  return v.toFixed(0);
}

function fmtPct(v?: number | null, digits = 2) {
  if (v === null || v === undefined) return "-";
  return `${v.toFixed(digits)}%`;
}

function fmtNum(v?: number | null, digits = 1) {
  if (v === null || v === undefined) return "-";
  return v.toFixed(digits);
}

function fmtWinRate(v?: number | null) {
  if (v === null || v === undefined) return "-";
  return `${(v * 100).toFixed(1)}%`;
}

function HeaderHint({ label, hint }: { label: string; hint?: string }) {
  if (!hint) return <span>{label}</span>;
  return (
    <span title={hint} className="cursor-help border-b border-dotted border-slate-600 pb-0.5">
      {label}
    </span>
  );
}

function statusTone(status?: string | null) {
  if (status === "active") return "bg-emerald-500/15 text-emerald-300 border-emerald-700/50";
  if (status === "cooling" || status === "stale") return "bg-amber-500/15 text-amber-300 border-amber-700/50";
  if (status === "reversal_risk") return "bg-red-500/15 text-red-300 border-red-700/50";
  if (status === "insufficient_data") return "bg-slate-500/15 text-slate-300 border-slate-700/50";
  return "bg-slate-500/10 text-slate-300 border-slate-700/50";
}

function brokerWarnings(broker: any) {
  if (!broker) return [];
  const warnings: string[] = [];
  if ((broker.coverage_ratio || 0) < 0.8) warnings.push("coverage");
  if (broker.status && broker.status !== "active") warnings.push(broker.status);
  if ((broker.recency_sessions || 99) > 2) warnings.push("not_recent");
  if ((broker.recent_5_session_net || 0) < 0) warnings.push("recent_5_negative");
  if (broker.retail_distribution_risk) warnings.push("retail_distribution_risk");
  return [...new Set(warnings)];
}

function screenerTradeStatus(row: any, broker: any) {
  return evaluateTradeStatus({
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
    one_month: broker || {},
  });
}

function flattenBacktestSummary(backtest?: BrokerBacktestPayload | null) {
  if (!backtest) return [];
  return Object.entries(backtest.summary_by_label).flatMap(([label, byHorizon]) => {
    const row: Record<string, string | number | null> = { label };
    for (const [horizon, metrics] of Object.entries(byHorizon)) {
      row[`count_${horizon}`] = metrics.count;
      row[`avg_${horizon}`] = metrics.avg_return_pct ?? null;
      row[`median_${horizon}`] = metrics.median_return_pct ?? null;
      row[`win_${horizon}`] = metrics.win_rate ?? null;
    }
    return [row];
  });
}

function flattenBacktestLiquiditySummary(backtest?: BrokerBacktestPayload | null) {
  if (!backtest) return [];
  return Object.entries(backtest.summary_by_label_and_liquidity).flatMap(([label, liquidityMap]) =>
    Object.entries(liquidityMap).map(([bucket, byHorizon]) => {
      const row: Record<string, string | number | null> = { label, liquidity_bucket: bucket };
      for (const [horizon, metrics] of Object.entries(byHorizon)) {
        row[`count_${horizon}`] = metrics.count;
        row[`avg_${horizon}`] = metrics.avg_return_pct ?? null;
        row[`win_${horizon}`] = metrics.win_rate ?? null;
      }
      return row;
    }),
  );
}

export default function ScreenerPage() {
  const pathname = usePathname();
  const isAiScreener = pathname === "/ai-screener";
  const [mode, setMode] = useState<"general" | "broker">("broker");
  const [methods, setMethods] = useState<string[]>([]);
  const [bandar, setBandar] = useState<string[]>([]);
  const [phases, setPhases] = useState<string[]>([]);
  const [minComposite, setMinComposite] = useState(60);
  const [requireForeign, setRequireForeign] = useState(false);
  const [breakout, setBreakout] = useState(false);
  const [requireBroker, setRequireBroker] = useState(true);
  const [brokerPeriodDays, setBrokerPeriodDays] = useState(30);
  const [brokerLabelMin, setBrokerLabelMin] = useState("accumulation");
  const [minBrokerMcap, setMinBrokerMcap] = useState(0.05);
  const [minBrokerAdv, setMinBrokerAdv] = useState(0.5);
  const [minBrokerDays, setMinBrokerDays] = useState(3);
  const [minBrokerPositiveRatio, setMinBrokerPositiveRatio] = useState(0.5);
  const [minCoverageRatio, setMinCoverageRatio] = useState(0.8);
  const [maxBalanceRatio, setMaxBalanceRatio] = useState(0.05);
  const [minBrokerConviction, setMinBrokerConviction] = useState(55);
  const [minEntryReadiness, setMinEntryReadiness] = useState(45);
  const [excludeStale, setExcludeStale] = useState(true);
  const [excludeReversalRisk, setExcludeReversalRisk] = useState(true);
  const [excludeInsufficientData, setExcludeInsufficientData] = useState(true);
  const [requireRecent, setRequireRecent] = useState(true);
  const [requireAcceleration, setRequireAcceleration] = useState(false);
  const [requireClusterConfirmation, setRequireClusterConfirmation] = useState(false);
  const [tradeStatusFilter, setTradeStatusFilter] = useState("all");
  const [setupFilter, setSetupFilter] = useState<SetupFilter>("all");
  const [sortBy, setSortBy] = useState("combined_rank");
  const [brokerRankWeight, setBrokerRankWeight] = useState(0.7);
  const [entryRankWeight, setEntryRankWeight] = useState(0.3);
  const [universe, setUniverse] = useState("idx");
  const [topN, setTopN] = useState(20);
  const [results, setResults] = useState<any[]>([]);
  const [backtest, setBacktest] = useState<BrokerBacktestPayload | null>(null);
  const [backtestLookbackDays, setBacktestLookbackDays] = useState(30);
  const [backtestSampleLimit, setBacktestSampleLimit] = useState(8);
  const [snapshotAt, setSnapshotAt] = useState<string | null>(null);
  const [snapshotRunId, setSnapshotRunId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  const [backtestLoading, setBacktestLoading] = useState(false);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [aiAnalysis, setAiAnalysis] = useState<any>(null);
  const [analysisProvider, setAnalysisProvider] = useState("");
  const [promptLoading, setPromptLoading] = useState(false);
  const [aiPrompt, setAiPrompt] = useState("");
  const [promptErr, setPromptErr] = useState("");
  const [promptMsg, setPromptMsg] = useState("");
  const [err, setErr] = useState("");
  const [backtestErr, setBacktestErr] = useState("");

  function toggle(arr: string[], set: (v: string[]) => void, v: string) {
    set(arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);
  }

  useEffect(() => {
    setSnapshotLoading(true);
    api.get("/screener/latest")
      .then((r) => {
        if (!r.data) return;
        setResults(r.data.results || []);
        setSnapshotAt(r.data.created_at || null);
        setSnapshotRunId(r.data.run_id || null);
      })
      .catch(() => {})
      .finally(() => setSnapshotLoading(false));
  }, []);

  async function loadBacktest() {
    setBacktestLoading(true);
    setBacktestErr("");
    try {
      const qs = new URLSearchParams({
        period_days: String(brokerPeriodDays),
        lookback_days: String(backtestLookbackDays),
        universe,
        min_label_score: String(minBrokerConviction),
        sample_limit: String(backtestSampleLimit),
      });
      const response = await fetch(`/api/screener/backtest?${qs.toString()}`, { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || payload?.message || "Failed to load backtest");
      }
      setBacktest(payload);
    } catch (e: any) {
      setBacktestErr(e.message || "Failed to load backtest");
    } finally {
      setBacktestLoading(false);
    }
  }

  useEffect(() => {
    if (mode === "broker") {
      setRequireBroker(true);
      setSortBy("combined_rank");
    } else {
      setRequireBroker(false);
      setSortBy("composite");
    }
  }, [mode]);

  async function run(overrides: { requireBroker?: boolean; sortBy?: string } = {}) {
    const effectiveRequireBroker = overrides.requireBroker ?? requireBroker;
    const effectiveSortBy = overrides.sortBy ?? sortBy;
    setLoading(true); setErr("");
    try {
      const scoreConfig = {
        accumulation_min_score: brokerLabelMin === "accumulation" ? minBrokerConviction : undefined,
        big_accumulation_min_score: brokerLabelMin === "big_accumulation" ? minBrokerConviction : undefined,
        aggressive_accumulation_min_score: brokerLabelMin === "aggressive_accumulation" ? minBrokerConviction : undefined,
      };
      const response = await fetch("/api/screener/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
        body: JSON.stringify({
          methods, bandar_labels: bandar, phases,
          min_composite: minComposite, require_foreign_inflow: requireForeign,
          breakout_filter: breakout, universe, top_n: topN,
          require_broker_accumulation: effectiveRequireBroker,
          broker_period_days: brokerPeriodDays,
          min_broker_net_pct_mcap: minBrokerMcap,
          min_broker_net_pct_adv: minBrokerAdv,
          min_broker_active_days: minBrokerDays,
          min_broker_positive_ratio: minBrokerPositiveRatio,
          min_broker_coverage_ratio: minCoverageRatio,
          max_broker_balance_ratio: maxBalanceRatio,
          min_broker_conviction_score: minBrokerConviction,
          min_entry_readiness_score: minEntryReadiness,
          exclude_stale: excludeStale,
          exclude_reversal_risk: excludeReversalRisk,
          exclude_insufficient_data: excludeInsufficientData,
          require_recent: requireRecent,
          require_acceleration: requireAcceleration,
          require_cluster_confirmation: requireClusterConfirmation,
          sort_by: effectiveSortBy,
          broker_rank_weight: brokerRankWeight,
          entry_rank_weight: entryRankWeight,
          broker_score_config: scoreConfig,
        }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || payload?.message || "Failed to run screener");
      }
      setResults(payload.results);
      setSnapshotAt(payload.created_at || null);
      setSnapshotRunId(payload.run_id || null);
    } catch (e: any) { setErr(e.message || "Failed to run screener"); }
    setLoading(false);
  }

  const renderedResults = results
    .map((row) => {
      const broker = row.dominant_factors?.broker_accumulation;
      const tradeStatus = requireBroker ? screenerTradeStatus(row, broker) : null;
      const setup = requireBroker ? normalizeTradeSetup(row, broker) : null;
      return { row, broker, tradeStatus, setup };
    })
    .filter((item) => tradeStatusFilter === "all" || item.tradeStatus?.code === tradeStatusFilter)
    .filter((item) => !requireBroker || setupMatchesFilter(item.setup!, setupFilter, item.tradeStatus?.code));
  const promptCandidates = renderedResults
    .filter((item) => item.tradeStatus?.code === "ready" || item.tradeStatus?.code === "waiting")
    .slice(0, 10);

  function candidatePayload() {
    return promptCandidates.map(({ row, broker, tradeStatus, setup }) => ({
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
  }

  async function buildAiPrompt() {
    setPromptLoading(true);
    setPromptErr("");
    setPromptMsg("");
    try {
      const candidates = candidatePayload();
      const response = await fetch("/api/screener/trade-candidates-prompt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
        body: JSON.stringify({ candidates, max_candidates: 10 }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || payload?.message || "Failed to build AI prompt.");
      }
      setAiPrompt(payload.prompt || "");
      setPromptMsg(`Prompt dibuat untuk ${payload.candidate_count || candidates.length} kandidat.`);
    } catch (e: any) {
      setPromptErr(e.response?.data?.detail || e.message || "Failed to build AI prompt.");
    } finally {
      setPromptLoading(false);
    }
  }

  async function runAiAnalysis() {
    setAnalysisLoading(true);
    setPromptErr("");
    setPromptMsg("");
    setAiAnalysis(null);
    try {
      const candidates = candidatePayload();
      const response = await fetch("/api/screener/trade-candidates-analysis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
        body: JSON.stringify({ candidates, max_candidates: 10 }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || payload?.message || "AI analysis failed.");
      }
      setAiAnalysis(payload.content || {});
      setAnalysisProvider(payload.provider || "");
      setPromptMsg(`AI selesai menganalisis ${payload.candidate_count || candidates.length} kandidat.`);
    } catch (e: any) {
      setPromptErr(e.response?.data?.detail || e.message || "AI analysis failed.");
    } finally {
      setAnalysisLoading(false);
    }
  }

  async function copyAiPrompt() {
    if (!aiPrompt) return;
    try {
      await navigator.clipboard.writeText(aiPrompt);
      setPromptMsg("Prompt copied to clipboard.");
    } catch {
      setPromptErr("Clipboard tidak tersedia. Select textarea lalu copy manual.");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">{isAiScreener ? "AI Screener" : "Screener"}</h1>
          <p className="text-sm text-slate-400 mt-1">
            {isAiScreener
              ? "Cari kandidat siap entry atau mendekati, lalu jalankan AI untuk analisis ranking, konfirmasi, dan risiko."
              : "Snapshot terbaru langsung ditampilkan. Jalankan ulang hanya saat perlu filter custom atau refresh manual."}
          </p>
        </div>
        <div className="text-right text-xs text-slate-500">
          <div>{snapshotLoading ? "Loading snapshot..." : snapshotAt ? `Snapshot ${new Date(snapshotAt).toLocaleString()}` : "No snapshot yet"}</div>
          {snapshotRunId && <div>Run #{snapshotRunId}</div>}
        </div>
      </div>
      <div className="card space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <button
            className={mode === "broker" ? "btn text-xs" : "btn-secondary text-xs"}
            onClick={() => {
              setMode("broker");
              setRequireBroker(true);
              setSortBy("combined_rank");
              run({ requireBroker: true, sortBy: "combined_rank" });
            }}
            disabled={loading}
          >
            Broker Accumulation
          </button>
          <button
            className={mode === "general" ? "btn text-xs" : "btn-secondary text-xs"}
            onClick={() => {
              setMode("general");
              setRequireBroker(false);
              setSortBy("composite");
              run({ requireBroker: false, sortBy: "composite" });
            }}
            disabled={loading}
          >
            General Screener
          </button>
        </div>
        <div>
          <h3 className="text-sm text-slate-400 mb-1">Technical methods (score ≥ 60)</h3>
          <div className="flex flex-wrap gap-2">
            {METHODS.map((m) => (
              <button key={m} onClick={() => toggle(methods, setMethods, m)}
                className={methods.includes(m) ? "btn text-xs" : "btn-secondary text-xs"}>{m}</button>
            ))}
          </div>
        </div>
        <div>
          <h3 className="text-sm text-slate-400 mb-1">Bandarmology labels (detected)</h3>
          <div className="flex flex-wrap gap-2">
            {BANDAR.map((m) => (
              <button key={m} onClick={() => toggle(bandar, setBandar, m)}
                className={bandar.includes(m) ? "btn text-xs" : "btn-secondary text-xs"}>{m}</button>
            ))}
          </div>
        </div>
        <div>
          <h3 className="text-sm text-slate-400 mb-1">Phases</h3>
          <div className="flex flex-wrap gap-2">
            {PHASES.map((m) => (
              <button key={m} onClick={() => toggle(phases, setPhases, m)}
                className={phases.includes(m) ? "btn text-xs" : "btn-secondary text-xs"}>{m}</button>
            ))}
          </div>
        </div>
        {requireBroker && (
          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <h3 className="text-sm text-slate-400 mb-1">Trade status</h3>
              <div className="flex flex-wrap gap-2">
                {TRADE_STATUS_FILTERS.map(([value, label]) => (
                  <button key={value} onClick={() => setTradeStatusFilter(value)}
                    className={tradeStatusFilter === value ? "btn text-xs" : "btn-secondary text-xs"}>{label}</button>
                ))}
              </div>
            </div>
            <div>
              <h3 className="text-sm text-slate-400 mb-1">Setup</h3>
              <div className="flex flex-wrap gap-2">
                {SETUP_FILTERS.map(([value, label]) => (
                  <button key={value} onClick={() => setSetupFilter(value)}
                    className={setupFilter === value ? "btn text-xs" : "btn-secondary text-xs"}>{label}</button>
                ))}
              </div>
            </div>
          </div>
        )}
        <div className="grid grid-cols-3 gap-3">
          <div><label className="text-sm text-slate-400">Min composite</label><input type="number" className="input" value={minComposite} onChange={(e) => setMinComposite(+e.target.value)} /></div>
          <div><label className="text-sm text-slate-400">Universe</label><select className="input" value={universe} onChange={(e) => setUniverse(e.target.value)}><option value="idx">IDX</option><option value="watchlist">Watchlist</option></select></div>
          <div><label className="text-sm text-slate-400">Top N</label><input type="number" className="input" value={topN} onChange={(e) => setTopN(+e.target.value)} /></div>
        </div>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={requireForeign} onChange={(e) => setRequireForeign(e.target.checked)} /> Require foreign inflow</label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={breakout} onChange={(e) => setBreakout(e.target.checked)} /> Breakout filter (EMA5&gt;EMA20, RSI&gt;45 rising, Close&gt;High3, Vol≥80%)</label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={requireBroker} onChange={(e) => setRequireBroker(e.target.checked)} /> Require broker accumulation</label>
        {requireBroker && (
          <div className="space-y-3 rounded-lg border border-slate-800 bg-slate-950/60 p-4">
            <div className="grid grid-cols-4 gap-3">
              <div>
                <label className="text-sm text-slate-400">Preset label</label>
                <select className="input" value={brokerLabelMin} onChange={(e) => setBrokerLabelMin(e.target.value)}>
                  {BROKER_LABELS.map((label) => <option key={label} value={label}>{label}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm text-slate-400">Broker period</label>
                <select className="input" value={brokerPeriodDays} onChange={(e) => setBrokerPeriodDays(+e.target.value)}>
                  <option value={7}>1W</option><option value={30}>1M</option>
                </select>
              </div>
              <div><label className="text-sm text-slate-400">Min conviction</label><input type="number" step="1" className="input" value={minBrokerConviction} onChange={(e) => setMinBrokerConviction(+e.target.value)} /></div>
              <div><label className="text-sm text-slate-400">Min entry readiness</label><input type="number" step="1" className="input" value={minEntryReadiness} onChange={(e) => setMinEntryReadiness(+e.target.value)} /></div>
            </div>
            <div className="grid grid-cols-4 gap-3">
              <div><label className="text-sm text-slate-400">Min %MCap</label><input type="number" step="0.01" className="input" value={minBrokerMcap} onChange={(e) => setMinBrokerMcap(+e.target.value)} /></div>
              <div><label className="text-sm text-slate-400">Min Days ADV</label><input type="number" step="0.1" className="input" value={minBrokerAdv} onChange={(e) => setMinBrokerAdv(+e.target.value)} /></div>
              <div><label className="text-sm text-slate-400">Min positive days</label><input type="number" className="input" value={minBrokerDays} onChange={(e) => setMinBrokerDays(+e.target.value)} /></div>
              <div><label className="text-sm text-slate-400">Min positive ratio</label><input type="number" step="0.05" className="input" value={minBrokerPositiveRatio} onChange={(e) => setMinBrokerPositiveRatio(+e.target.value)} /></div>
            </div>
            <div className="grid grid-cols-4 gap-3">
              <div><label className="text-sm text-slate-400">Min coverage</label><input type="number" step="0.05" className="input" value={minCoverageRatio} onChange={(e) => setMinCoverageRatio(+e.target.value)} /></div>
              <div><label className="text-sm text-slate-400">Max balance ratio</label><input type="number" step="0.01" className="input" value={maxBalanceRatio} onChange={(e) => setMaxBalanceRatio(+e.target.value)} /></div>
              <div><label className="text-sm text-slate-400">Broker rank weight</label><input type="number" step="0.05" className="input" value={brokerRankWeight} onChange={(e) => setBrokerRankWeight(+e.target.value)} /></div>
              <div><label className="text-sm text-slate-400">Entry rank weight</label><input type="number" step="0.05" className="input" value={entryRankWeight} onChange={(e) => setEntryRankWeight(+e.target.value)} /></div>
            </div>
            <div className="grid grid-cols-3 gap-3 text-sm">
              <label className="flex items-center gap-2"><input type="checkbox" checked={excludeStale} onChange={(e) => setExcludeStale(e.target.checked)} /> Exclude stale</label>
              <label className="flex items-center gap-2"><input type="checkbox" checked={excludeReversalRisk} onChange={(e) => setExcludeReversalRisk(e.target.checked)} /> Exclude reversal risk</label>
              <label className="flex items-center gap-2"><input type="checkbox" checked={excludeInsufficientData} onChange={(e) => setExcludeInsufficientData(e.target.checked)} /> Exclude insufficient data</label>
              <label className="flex items-center gap-2"><input type="checkbox" checked={requireRecent} onChange={(e) => setRequireRecent(e.target.checked)} /> Require recent buy</label>
              <label className="flex items-center gap-2"><input type="checkbox" checked={requireAcceleration} onChange={(e) => setRequireAcceleration(e.target.checked)} /> Require acceleration</label>
              <label className="flex items-center gap-2"><input type="checkbox" checked={requireClusterConfirmation} onChange={(e) => setRequireClusterConfirmation(e.target.checked)} /> Require cluster confirmation</label>
            </div>
            <div>
              <label className="text-sm text-slate-400">Sort by</label>
              <select className="input max-w-xs" value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
                {SORT_OPTIONS.map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>
          </div>
        )}
        <div className="text-xs text-slate-500">
          {mode === "broker"
            ? "Broker accumulation mode memprioritaskan saham dengan conviction broker kuat, coverage cukup, dan ranking gabungan broker + entry."
            : "General screener memakai ranking composite biasa. Filter broker tidak diwajibkan kecuali Anda centang manual."}
        </div>
        <button className="btn" onClick={() => run()} disabled={loading}>{loading ? "Running..." : "Refresh / Run Custom Screener"}</button>
        {err && <p className="text-sm text-red-400">{err}</p>}
      </div>

      <div className="card space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="font-semibold">Broker Backtest Baseline</h2>
            <p className="mt-1 text-sm text-slate-400">
              Validasi kasar label broker terhadap forward return 5/10/20 sesi untuk cek apakah threshold saat ini punya edge awal. Default lookback diset 30 hari agar sesuai coverage broker saat ini. Backtest tidak dimuat otomatis agar halaman screener tetap ringan.
            </p>
          </div>
          <div className="text-right text-xs text-slate-500">
            <div>{backtestLoading ? "Loading backtest..." : backtest?.as_of_date ? `As of ${backtest.as_of_date}` : "No backtest yet"}</div>
            {backtest && <div>{backtest.period_days === 7 ? "1W" : "1M"} window • {backtest.universe.toUpperCase()}</div>}
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-4">
          <div>
            <label className="text-sm text-slate-400">Lookback days</label>
            <input type="number" className="input" value={backtestLookbackDays} onChange={(e) => setBacktestLookbackDays(+e.target.value)} />
          </div>
          <div>
            <label className="text-sm text-slate-400">Sample limit</label>
            <input type="number" className="input" value={backtestSampleLimit} onChange={(e) => setBacktestSampleLimit(+e.target.value)} />
          </div>
          <div>
            <label className="text-sm text-slate-400">Min label score</label>
            <input type="number" className="input" value={minBrokerConviction} onChange={(e) => setMinBrokerConviction(+e.target.value)} />
          </div>
          <div className="flex items-end">
            <button className="btn w-full" onClick={loadBacktest} disabled={backtestLoading}>
              {backtestLoading ? "Refreshing..." : "Refresh Backtest"}
            </button>
          </div>
        </div>

        {backtestErr && <p className="text-sm text-red-400">{backtestErr}</p>}

        {backtest && (
          <>
            <div className="grid gap-3 md:grid-cols-4">
              <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                <div className="text-xs uppercase tracking-wide text-slate-500">Horizon</div>
                <div className="mt-1 text-lg font-semibold text-white">{backtest.horizons.join(" / ")}D</div>
              </div>
              <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                <div className="text-xs uppercase tracking-wide text-slate-500">Lookback</div>
                <div className="mt-1 text-lg font-semibold text-white">{backtest.lookback_days} hari</div>
              </div>
              <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                <div className="text-xs uppercase tracking-wide text-slate-500">Samples</div>
                <div className="mt-1 text-lg font-semibold text-white">{backtest.samples.length}</div>
              </div>
              <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                <div className="text-xs uppercase tracking-wide text-slate-500">Universe</div>
                <div className="mt-1 text-lg font-semibold text-white">{backtest.universe.toUpperCase()}</div>
              </div>
            </div>

            <div className="space-y-2">
              <h3 className="text-sm font-medium text-slate-200">Summary by label</h3>
              <DataTable
                linkKeys={[]}
                columns={[
                  { key: "label", label: "Label" },
                  { key: "count_5", label: "N 5D" },
                  { key: "avg_5", label: "Avg 5D", format: (v) => fmtPct(v, 2) },
                  { key: "median_5", label: "Median 5D", format: (v) => fmtPct(v, 2) },
                  { key: "win_5", label: "Win 5D", format: (v) => fmtWinRate(v) },
                  { key: "count_10", label: "N 10D" },
                  { key: "avg_10", label: "Avg 10D", format: (v) => fmtPct(v, 2) },
                  { key: "win_10", label: "Win 10D", format: (v) => fmtWinRate(v) },
                  { key: "count_20", label: "N 20D" },
                  { key: "avg_20", label: "Avg 20D", format: (v) => fmtPct(v, 2) },
                  { key: "win_20", label: "Win 20D", format: (v) => fmtWinRate(v) },
                ]}
                rows={flattenBacktestSummary(backtest)}
              />
            </div>

            <div className="space-y-2">
              <h3 className="text-sm font-medium text-slate-200">Summary by label x liquidity</h3>
              <DataTable
                linkKeys={[]}
                columns={[
                  { key: "label", label: "Label" },
                  { key: "liquidity_bucket", label: "Liquidity" },
                  { key: "count_5", label: "N 5D" },
                  { key: "avg_5", label: "Avg 5D", format: (v) => fmtPct(v, 2) },
                  { key: "win_5", label: "Win 5D", format: (v) => fmtWinRate(v) },
                  { key: "count_10", label: "N 10D" },
                  { key: "avg_10", label: "Avg 10D", format: (v) => fmtPct(v, 2) },
                  { key: "count_20", label: "N 20D" },
                  { key: "avg_20", label: "Avg 20D", format: (v) => fmtPct(v, 2) },
                ]}
                rows={flattenBacktestLiquiditySummary(backtest)}
              />
            </div>

            <div className="space-y-2">
              <h3 className="text-sm font-medium text-slate-200">Sample windows</h3>
              <DataTable
                columns={[
                  { key: "ticker", label: "Ticker" },
                  { key: "date", label: "Date" },
                  { key: "label", label: "Label" },
                  { key: "score", label: "Score", format: (v) => fmtNum(v, 1) },
                  { key: "status", label: "Status" },
                  { key: "liquidity_bucket", label: "Liquidity" },
                  { key: "forward_5", label: "Fwd 5D", format: (v) => fmtPct(v, 2) },
                  { key: "forward_10", label: "Fwd 10D", format: (v) => fmtPct(v, 2) },
                  { key: "forward_20", label: "Fwd 20D", format: (v) => fmtPct(v, 2) },
                ]}
                rows={backtest.samples.map((sample) => ({
                  ...sample,
                  forward_5: sample.forward_returns_pct["5"],
                  forward_10: sample.forward_returns_pct["10"],
                  forward_20: sample.forward_returns_pct["20"],
                }))}
              />
            </div>
          </>
        )}
      </div>

      <div className="card">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-semibold">Results ({renderedResults.length}{renderedResults.length !== results.length ? ` of ${results.length}` : ""})</h2>
          {requireBroker && (
            <div className="flex flex-wrap items-center gap-2">
              <button className="btn text-xs" onClick={runAiAnalysis} disabled={analysisLoading || promptCandidates.length === 0}>
                {analysisLoading ? "Analyzing..." : "Analisis AI"}
              </button>
              <button className="btn-secondary text-xs" onClick={buildAiPrompt} disabled={promptLoading || promptCandidates.length === 0}>
                {promptLoading ? "Building prompt..." : "Buat Prompt AI"}
              </button>
              <button className="btn-secondary text-xs" onClick={copyAiPrompt} disabled={!aiPrompt}>Copy Prompt</button>
            </div>
          )}
        </div>
        {requireBroker && (
          <div className="mb-3 space-y-2">
            <p className="text-xs text-slate-500">
              Prompt memakai maksimal 10 kandidat `Siap Entry` atau `Tunggu Konfirmasi` dari hasil dan filter setup yang sedang tampil.
            </p>
            {promptErr && <p className="text-xs text-red-400">{promptErr}</p>}
            {promptMsg && <p className="text-xs text-emerald-300">{promptMsg}</p>}
            {aiAnalysis && (
              <div className="rounded border border-slate-800 bg-slate-950/70 p-3 text-sm">
                <div className="mb-2 text-xs text-slate-500">Provider: {analysisProvider || "-"}</div>
                {Array.isArray(aiAnalysis.top_candidates) && (
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
                )}
                {aiAnalysis.summary && <p className="mt-3 text-slate-300">{aiAnalysis.summary}</p>}
                {!Array.isArray(aiAnalysis.top_candidates) && (
                  <pre className="whitespace-pre-wrap text-xs text-slate-300">{JSON.stringify(aiAnalysis, null, 2)}</pre>
                )}
              </div>
            )}
            {aiPrompt && (
              <textarea
                className="input min-h-56 w-full font-mono text-xs"
                value={aiPrompt}
                onChange={(e) => setAiPrompt(e.target.value)}
              />
            )}
          </div>
        )}
        <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="text-slate-400"><th className="text-left">#</th><th>Ticker</th><th>Name</th><th>Score</th><th><HeaderHint label="Tech Phase" hint={COLUMN_HINTS.techPhase} /></th>{requireBroker && <><th><HeaderHint label="Trade" hint={COLUMN_HINTS.trade} /></th><th><HeaderHint label="Setup" hint={COLUMN_HINTS.setup} /></th><th><HeaderHint label="Target" hint={COLUMN_HINTS.setup} /></th><th><HeaderHint label="Jarak" hint={COLUMN_HINTS.distance} /></th><th>Invalidasi</th><th><HeaderHint label="Conviction" hint={COLUMN_HINTS.conviction} /></th><th><HeaderHint label="Flow" hint={COLUMN_HINTS.flow} /></th><th><HeaderHint label="Closest" hint={COLUMN_HINTS.closest} /></th><th><HeaderHint label="Entry" hint={COLUMN_HINTS.entry} /></th><th><HeaderHint label="Combined" hint={COLUMN_HINTS.combined} /></th><th><HeaderHint label="Status" hint={COLUMN_HINTS.status} /></th><th><HeaderHint label="Label" hint={COLUMN_HINTS.label} /></th><th><HeaderHint label="Broker / Cluster" hint={COLUMN_HINTS.broker} /></th><th><HeaderHint label="Net" hint={COLUMN_HINTS.net} /></th><th><HeaderHint label="%MCap" hint={COLUMN_HINTS.mcap} /></th><th><HeaderHint label="Days ADV" hint={COLUMN_HINTS.adv} /></th><th><HeaderHint label="Pos Days" hint={COLUMN_HINTS.pos} /></th><th><HeaderHint label="Last Buy" hint={COLUMN_HINTS.lastBuy} /></th><th><HeaderHint label="Warnings" hint={COLUMN_HINTS.warnings} /></th></>}</tr></thead>
          <tbody>
            {renderedResults.map(({ row: r, broker, tradeStatus, setup }) => {
              const warnings = brokerWarnings(broker);
              return (
                <tr key={r.ticker} className="border-t border-slate-800">
                  <td className="py-1">{r.rank}</td>
                  <td><TickerLink ticker={r.ticker} /></td>
                  <td>{r.name}</td>
                  <td className="text-center">{r.composite.toFixed(0)}</td>
                  <td className="text-center">{r.phase}</td>
                  {requireBroker && (
                    <>
                      <td className="text-center">
                        {tradeStatus && (
                          <div className="space-y-1">
                            <span className={`inline-flex rounded border px-2 py-0.5 text-xs ${tradeStatus.tone}`}>{tradeStatus.label}</span>
                            {(tradeStatus.blockers[0] || tradeStatus.warnings[0]) && (
                              <div className="text-[11px] text-slate-500">{tradeStatus.blockers[0] || tradeStatus.warnings[0]}</div>
                            )}
                          </div>
                        )}
                      </td>
                      <td className="text-center">
                        {setup && (
                          <div className="space-y-1">
                            <span className={`inline-flex rounded border px-2 py-0.5 text-xs ${setupTone(setup)}`}>{setup.label || "-"}</span>
                            {(setup.blockers[0] || setup.confirmations[0]) && (
                              <div className="text-[11px] text-slate-500">{setupReasonText(setup.blockers[0] || setup.confirmations[0])}</div>
                            )}
                          </div>
                        )}
                      </td>
                      <td className="text-center font-mono text-amber-200">{setup ? setupTargetText(setup) : "-"}</td>
                      <td className="text-center font-mono text-slate-300">{setup?.distance_pct !== null && setup?.distance_pct !== undefined ? `${setup.distance_pct.toFixed(2)}%` : "-"}</td>
                      <td className="text-center font-mono text-red-200">{setup?.invalidation_price !== null && setup?.invalidation_price !== undefined ? setup.invalidation_price.toFixed(0) : "-"}</td>
                      <td className="text-center font-mono text-amber-300">{r.broker_conviction_score?.toFixed(1) ?? "-"}</td>
                      <td className="text-center">
                        <div className="font-mono text-cyan-300">{r.flow_quality_score?.toFixed(1) ?? "-"}</div>
                        <div className="text-[11px] text-slate-500">{r.flow_quality_label ?? "-"}</div>
                      </td>
                      <td className="text-center">
                        {r.closest_to_smart_rank ? (
                          <div>
                            <div className="font-mono text-emerald-300">#{r.closest_to_smart_rank}</div>
                            <div className="text-[11px] text-slate-500">{r.closest_to_smart_score?.toFixed(1) ?? "-"}</div>
                          </div>
                        ) : (
                          <span className="text-slate-500">-</span>
                        )}
                      </td>
                      <td className="text-center font-mono text-sky-300">{r.entry_readiness_score?.toFixed(1) ?? "-"}</td>
                      <td className="text-center font-mono text-white">{r.combined_rank_score?.toFixed(1) ?? "-"}</td>
                      <td className="text-center"><span className={`inline-flex rounded border px-2 py-0.5 text-xs ${statusTone(r.broker_status)}`}>{r.broker_status ?? "-"}</span></td>
                      <td className="text-center text-emerald-300">{r.broker_conviction_label ?? "-"}</td>
                      <td className="text-left">
                        <div className="font-mono text-indigo-400">{broker?.top_broker ?? "-"}</div>
                        <div className="text-xs text-slate-500">{(broker?.cluster_brokers || []).join(", ") || "-"}</div>
                      </td>
                      <td className="text-center font-mono text-emerald-400">{broker ? fmtMoney(broker.net) : "-"}</td>
                      <td className="text-center text-emerald-400">{fmtPct(broker?.pct_market_cap, 4)}</td>
                      <td className="text-center text-slate-300">{fmtNum(broker?.days_of_adv, 2)}</td>
                      <td className="text-center text-slate-400">{broker ? `${broker.positive_days}/${broker.trading_days} (${fmtPct((broker.positive_ratio || 0) * 100, 1)})` : "-"}</td>
                      <td className="text-center text-slate-300">{broker?.last_buy_date ?? "-"}</td>
                      <td className="text-left">
                        <div className="flex flex-wrap gap-1">
                          {warnings.length ? warnings.map((warning) => (
                            <span key={warning} className="rounded border border-slate-700 bg-slate-900 px-1.5 py-0.5 text-[11px] text-slate-300">{warning}</span>
                          )) : <span className="text-xs text-slate-500">clean</span>}
                        </div>
                      </td>
                    </>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
        </div>
      </div>
    </div>
  );
}
