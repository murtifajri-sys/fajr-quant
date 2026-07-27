import { api } from "@/lib/api";
import { PipelineActions } from "@/components/PipelineActions";
import { PipelineTable } from "@/components/PipelineTable";
import { TickerLink } from "@/components/TickerLink";
import { TokenWarning } from "@/components/TokenWarning";
import { normalizeTradeSetup, setupReasonText, setupTargetText } from "@/lib/tradeSetup";

export const dynamic = "force-dynamic";

function fmtPct(v?: number | null, digits = 1) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return "-";
  return `${Number(v).toFixed(digits)}%`;
}

function fmtNum(v?: number | null, digits = 1) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return "-";
  return Number(v).toFixed(digits);
}

function fmtMoney(v?: number | null) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return "-";
  const n = Math.abs(Number(v));
  if (n >= 1e12) return `${(Number(v) / 1e12).toFixed(1)}T`;
  if (n >= 1e9) return `${(Number(v) / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(Number(v) / 1e6).toFixed(0)}M`;
  return Number(v).toFixed(0);
}

function statusClass(status?: string | null) {
  if (status === "SUCCESS") return "border-emerald-700/50 bg-emerald-500/10 text-emerald-300";
  if (status === "FAILURE" || status === "ORPHANED") return "border-red-700/50 bg-red-500/10 text-red-300";
  if (status === "CANCELLED") return "border-slate-700 bg-slate-800 text-slate-300";
  return "border-amber-700/50 bg-amber-500/10 text-amber-200";
}

function setupClass(setupType?: string | null) {
  if (setupType === "buy_on_weakness") return "text-cyan-300";
  if (setupType === "wait_breakout" || setupType === "wait_retest") return "text-amber-200";
  if (setupType === "wait_value_area") return "text-sky-300";
  return "text-slate-400";
}

export default async function Dashboard() {
  let recs: any[] = [];
  let latest: any = null;
  let monitorRows: any[] = [];
  let runs: any[] = [];
  let watchlist: any[] = [];
  let backendOk = true;

  try {
    const [recRes, screenRes, monitorRes, runRes, watchRes] = await Promise.allSettled([
      api.get("/data/recommendations", { params: { limit: 8 } }),
      api.get("/screener/latest"),
      api.get("/screener/trade-monitor", { params: { limit: 12 } }),
      api.get("/tasks/runs", { params: { limit: 10 } }),
      api.get("/watchlist"),
    ]);
    if (recRes.status === "fulfilled") recs = recRes.value.data?.items || recRes.value.data || [];
    if (screenRes.status === "fulfilled") latest = screenRes.value.data;
    if (monitorRes.status === "fulfilled") monitorRows = monitorRes.value.data || [];
    if (runRes.status === "fulfilled") runs = runRes.value.data || [];
    if (watchRes.status === "fulfilled") watchlist = watchRes.value.data || [];
    backendOk = [recRes, screenRes, runRes, watchRes].some((result) => result.status === "fulfilled");
  } catch {
    backendOk = false;
  }

  const activeRun = runs.find((run: any) => ["PROGRESS", "QUEUED", "STARTED"].includes(run.status));
  const backfillRun = runs.find((run: any) => run.task_name === "broker_flow_backfill");
  const screenerRows = latest?.results || [];
  const brokerRows = screenerRows.filter((row: any) => row.broker_conviction_score !== null && row.broker_conviction_score !== undefined);
  const tradeRows = monitorRows.length > 0 ? monitorRows : brokerRows.slice(0, 8);
  const tradeCandidates = tradeRows.map((row: any) => {
    const broker = row.dominant_factors?.broker_accumulation;
    const setup = normalizeTradeSetup(row, broker);
    return { row, broker, setup };
  });
  const smartLikeCount = brokerRows.filter((row: any) => row.flow_quality_label === "smart_like_accumulation").length;
  const latestRecommendationDate = recs[0]?.date || null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="mt-1 text-sm text-slate-400">
            Ringkasan pipeline, screener broker, kandidat entry, dan watchlist.
          </p>
        </div>
        <PipelineActions />
      </div>

      <TokenWarning />

      {!backendOk && (
        <div className="card border-red-900/60 bg-red-950/30">
          <h2 className="font-semibold text-red-200">Backend tidak terbaca</h2>
          <p className="mt-1 text-sm text-red-100/80">Dashboard belum bisa mengambil data API lokal.</p>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-4">
        <div className="card">
          <div className="text-xs uppercase tracking-wide text-slate-500">Pipeline</div>
          <div className="mt-2 text-2xl font-semibold text-white">{activeRun ? activeRun.status : "Idle"}</div>
          <div className="mt-1 text-xs text-slate-400">{activeRun?.stage || "Tidak ada task aktif"}</div>
        </div>
        <div className="card">
          <div className="text-xs uppercase tracking-wide text-slate-500">Backfill Broker</div>
          <div className="mt-2 text-2xl font-semibold text-amber-100">
            {backfillRun ? `${backfillRun.processed_tickers || 0}/${backfillRun.total_tickers || 0}` : "-"}
          </div>
          <div className="mt-1 text-xs text-slate-400">{backfillRun ? `${backfillRun.progress || 0}% - failed ${backfillRun.failed_tickers || 0}` : "Belum ada run"}</div>
        </div>
        <div className="card">
          <div className="text-xs uppercase tracking-wide text-slate-500">Screener Snapshot</div>
          <div className="mt-2 text-2xl font-semibold text-white">{screenerRows.length}</div>
          <div className="mt-1 text-xs text-slate-400">{latest?.created_at ? new Date(latest.created_at).toLocaleString() : "Belum ada snapshot"}</div>
        </div>
        <div className="card">
          <div className="text-xs uppercase tracking-wide text-slate-500">Smart-like Flow</div>
          <div className="mt-2 text-2xl font-semibold text-emerald-300">{smartLikeCount}</div>
          <div className="mt-1 text-xs text-slate-400">dari {brokerRows.length} kandidat broker</div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="card lg:col-span-2">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="font-semibold">Trade Monitor</h2>
            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-500">{monitorRows.length > 0 ? "Top trade score" : "Fallback snapshot"}</span>
              <a href="/ai-screener" className="text-sm text-sky-300 underline-offset-4 hover:underline">AI Screener</a>
            </div>
          </div>
          {tradeCandidates.length === 0 ? (
            <p className="text-sm text-slate-400">Belum ada kandidat trade dari score dan broker flow terbaru.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-slate-400">
                  <th className="text-left">Ticker</th>
                  <th>Conv</th>
                  <th>Entry</th>
                  <th>Flow</th>
                  <th>Setup</th>
                  <th>Target</th>
                  <th>Jarak</th>
                </tr>
              </thead>
              <tbody>
                {tradeCandidates.map(({ row, broker, setup }: any) => (
                  <tr key={row.ticker} className="border-t border-slate-800">
                    <td className="py-2"><TickerLink ticker={row.ticker} /></td>
                    <td className="text-center font-mono text-amber-300">{fmtNum(row.broker_conviction_score)}</td>
                    <td className="text-center font-mono text-sky-300">{fmtNum(row.entry_readiness_score)}</td>
                    <td className="text-center">
                      <div className="font-mono text-cyan-300">{fmtNum(row.flow_quality_score)}</div>
                      <div className="text-[11px] text-slate-500">{row.flow_quality_label || broker?.flow_quality_label || "-"}</div>
                    </td>
                    <td className={`text-center ${setupClass(setup.setup_type)}`}>
                      <div>{setup.label || "-"}</div>
                      <div className="text-[11px] text-slate-500">{setupReasonText(setup.blockers?.[0] || setup.confirmations?.[0])}</div>
                    </td>
                    <td className="text-center font-mono text-slate-300">{setupTargetText(setup)}</td>
                    <td className="text-center font-mono text-slate-300">{setup.distance_pct !== null && setup.distance_pct !== undefined ? fmtPct(setup.distance_pct, 2) : "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="card">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="font-semibold">Watchlist</h2>
            <a href="/watchlist" className="text-sm text-sky-300 underline-offset-4 hover:underline">Kelola</a>
          </div>
          {watchlist.length === 0 ? (
            <p className="text-sm text-slate-400">Watchlist masih kosong.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {watchlist.slice(0, 24).map((item: any) => (
                <a
                  key={`${item.name}-${item.ticker}`}
                  href={`/charts/${item.ticker}`}
                  className="rounded border border-slate-700 bg-slate-950 px-2.5 py-1 text-sm font-mono text-sky-300 hover:border-sky-700"
                >
                  {item.ticker}
                </a>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="font-semibold">Latest Recommendations</h2>
            <div className="text-xs text-slate-500">{latestRecommendationDate ? `Latest ${latestRecommendationDate}` : "No data"}</div>
          </div>
          {recs.length === 0 ? (
            <p className="text-slate-400 text-sm">Belum ada rekomendasi tersimpan.</p>
          ) : (
            <table className="w-full text-sm">
              <thead><tr className="text-slate-400"><th className="text-left">Ticker</th><th>Date</th><th>Action</th><th>Entry</th><th>Target</th></tr></thead>
              <tbody>
                {recs.slice(0, 8).map((r, i) => (
                  <tr key={`${r.ticker}-${r.date}-${i}`} className="border-t border-slate-800">
                    <td className="py-1"><TickerLink ticker={r.ticker} /></td>
                    <td className="text-center text-xs text-slate-400">{r.date || "-"}</td>
                    <td className="text-center">{r.action}</td>
                    <td className="text-center">{r.entry ?? "-"}</td>
                    <td className="text-center">{r.target ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="card">
          <h2 className="font-semibold mb-3">Quick Actions</h2>
          <div className="grid gap-2 sm:grid-cols-2">
            <a href="/screener" className="rounded border border-slate-800 bg-slate-950 p-3 hover:border-sky-800">
              <div className="font-medium text-sky-300">Screener</div>
              <div className="mt-1 text-xs text-slate-500">Filter broker, trade status, dan setup.</div>
            </a>
            <a href="/ai-screener" className="rounded border border-slate-800 bg-slate-950 p-3 hover:border-sky-800">
              <div className="font-medium text-sky-300">AI Screener</div>
              <div className="mt-1 text-xs text-slate-500">Ranking kandidat siap entry atau mendekati.</div>
            </a>
            <a href="/charts" className="rounded border border-slate-800 bg-slate-950 p-3 hover:border-sky-800">
              <div className="font-medium text-sky-300">Charts</div>
              <div className="mt-1 text-xs text-slate-500">Buka chart ticker dan status entry.</div>
            </a>
            <a href="/data" className="rounded border border-slate-800 bg-slate-950 p-3 hover:border-sky-800">
              <div className="font-medium text-sky-300">Data</div>
              <div className="mt-1 text-xs text-slate-500">Cek harga, score, technical, dan flow.</div>
            </a>
          </div>
        </div>
      </div>

      {activeRun && (
        <div className={`rounded-lg border p-4 ${statusClass(activeRun.status)}`}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-sm font-semibold">{activeRun.task_name}</div>
              <div className="mt-1 text-xs opacity-80">{activeRun.stage || "-"} - {activeRun.processed_tickers || 0}/{activeRun.total_tickers || 0} ticker</div>
            </div>
            <a href={`/tasks/${activeRun.task_id}`} className="text-sm underline-offset-4 hover:underline">Detail task</a>
          </div>
        </div>
      )}

      <PipelineTable runs={runs} />
    </div>
  );
}
