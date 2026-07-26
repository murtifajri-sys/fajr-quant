"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { evaluateTradeStatus } from "@/lib/tradeStatus";
import { BrokerAnalysisPanel, BrokerConvictionPanel, ScoreRadar, BandarPanel, ForeignFlowPanel, ScoreTimeline, HarmonicPanel, ElliottPanel, TopBrokerPanel } from "@/components/ChartPanels";

export default function ChartPage({ params }: { params: { ticker: string } }) {
  const router = useRouter();
  const ticker = params.ticker.toUpperCase();
  const [data, setData] = useState<any>(null);
  const [brokerDetail, setBrokerDetail] = useState<any>(null);
  const [error, setError] = useState("");
  const [days, setDays] = useState(180);
  const [brokerDays, setBrokerDays] = useState(30);
  const [chartTab, setChartTab] = useState<"broker" | "tradingview">("broker");
  const [loading, setLoading] = useState(false);
  const [input, setInput] = useState(ticker);
  const [watchlistIds, setWatchlistIds] = useState<string[]>([]);
  const [watchlistBusy, setWatchlistBusy] = useState(false);
  const [watchlistMsg, setWatchlistMsg] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    setInput(ticker);
    Promise.all([
      api.get(`/charts/${ticker}/overview`, { params: { days, broker_days: brokerDays } }),
      api.get(`/screener/broker/${ticker}`),
      api.get("/watchlist"),
    ])
      .then(([overview, broker, watchlist]) => {
        setData(overview.data);
        setBrokerDetail(broker.data);
        setWatchlistIds((watchlist.data || []).map((item: any) => String(item.ticker || "").toUpperCase()));
      })
      .catch(() => setError("Failed to load chart data"))
      .finally(() => setLoading(false));
  }, [ticker, days, brokerDays]);

  function go(e: React.FormEvent) {
    e.preventDefault();
    const t = input.trim().toUpperCase();
    if (t) router.push(`/charts/${t}`);
  }

  async function addToWatchlist() {
    setWatchlistBusy(true);
    setWatchlistMsg("Saving to watchlist...");
    try {
      await api.post("/watchlist", { ticker, name: "default", sort_order: watchlistIds.length });
      setWatchlistIds((current) => (current.includes(ticker) ? current : [...current, ticker]));
      setWatchlistMsg("Ticker added to watchlist.");
    } catch (e: any) {
      setWatchlistMsg(e.response?.data?.detail || e.message || "Failed to add to watchlist.");
    } finally {
      setWatchlistBusy(false);
    }
  }

  const tradeStatus = evaluateTradeStatus(brokerDetail, { loading, hasError: Boolean(error) });
  const inWatchlist = watchlistIds.includes(ticker);
  const fmtMetric = (value: number | null, suffix = "") => (value === null ? "-" : `${value.toFixed(1)}${suffix}`);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold font-mono">{ticker}</h1>
        <div className="flex items-center gap-2">
          <form onSubmit={go} className="flex gap-2">
            <input
              className="input w-28 text-center font-mono text-sm"
              value={input}
              onChange={(e) => setInput(e.target.value.toUpperCase())}
              placeholder="Ticker"
            />
          </form>
          <select className="input w-24" value={days} onChange={(e) => setDays(+e.target.value)}>
            <option value={90}>90d</option><option value={180}>180d</option><option value={365}>365d</option>
          </select>
          <select className="input w-24" value={brokerDays} onChange={(e) => setBrokerDays(+e.target.value)}>
            <option value={7}>Broker 1W</option><option value={30}>Broker 1M</option>
          </select>
        </div>
      </div>
      <div className="grid gap-3 md:grid-cols-[1.4fr_1fr]">
        <div className={`rounded-xl border p-4 ${tradeStatus.tone}`}>
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Status Trade</div>
              <div className="mt-1 text-xl font-semibold">{tradeStatus.label}</div>
            </div>
            <a href="/watchlist" className="text-xs text-sky-300 underline-offset-4 hover:underline">Lihat watchlist</a>
          </div>
          <p className="mt-2 text-sm text-slate-300">{tradeStatus.summary}</p>
          <div className="mt-3 grid grid-cols-4 gap-2 text-[11px] text-slate-400">
            <div><span className="block text-slate-500">Conviction</span><span className="font-mono text-slate-200">{fmtMetric(tradeStatus.metrics.conviction)}</span></div>
            <div><span className="block text-slate-500">Entry</span><span className="font-mono text-slate-200">{fmtMetric(tradeStatus.metrics.entry)}</span></div>
            <div><span className="block text-slate-500">Flow</span><span className="font-mono text-slate-200">{fmtMetric(tradeStatus.metrics.flow)}</span></div>
            <div><span className="block text-slate-500">Recency</span><span className="font-mono text-slate-200">{fmtMetric(tradeStatus.metrics.recency, "s")}</span></div>
          </div>
          {(tradeStatus.passed.length > 0 || tradeStatus.blockers.length > 0 || tradeStatus.warnings.length > 0) && (
            <div className="mt-3 grid gap-2 text-xs md:grid-cols-3">
              {tradeStatus.passed.length > 0 && (
                <div>
                  <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Lolos</div>
                  <div className="mt-1 text-slate-300">{tradeStatus.passed.join(", ")}</div>
                </div>
              )}
              {tradeStatus.blockers.length > 0 && (
                <div>
                  <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Penahan</div>
                  <div className="mt-1 text-slate-300">{tradeStatus.blockers.join(", ")}</div>
                </div>
              )}
              {tradeStatus.warnings.length > 0 && (
                <div>
                  <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Warning</div>
                  <div className="mt-1 text-slate-300">{tradeStatus.warnings.join(", ")}</div>
                </div>
              )}
            </div>
          )}
          <p className="mt-3 text-[11px] text-slate-500">Status ini ringkasan sistem, bukan instruksi transaksi otomatis.</p>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Watchlist</div>
              <div className="mt-1 text-sm text-slate-300">
                {inWatchlist ? "Ticker ini sudah ada di watchlist default." : "Simpan ticker ini untuk pantauan cepat dari menu watchlist."}
              </div>
            </div>
            <button className="btn" onClick={addToWatchlist} disabled={watchlistBusy || inWatchlist}>
              {inWatchlist ? "On Watchlist" : watchlistBusy ? "Saving..." : "Add to Watchlist"}
            </button>
          </div>
          {watchlistMsg && <p className="mt-2 text-xs text-slate-400">{watchlistMsg}</p>}
        </div>
      </div>
      {loading && <p className="text-slate-400">Loading...</p>}
      {error && <p className="text-red-400">{error}</p>}
      {!loading && !error && data && (
        <div className="space-y-4">
          <div className="card">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h2 className="font-semibold">Price Chart</h2>
              <div className="flex rounded border border-slate-800 bg-slate-950 p-1 text-xs">
                <button
                  className={`rounded px-3 py-1 ${chartTab === "broker" ? "bg-sky-500/20 text-sky-300" : "text-slate-400"}`}
                  onClick={() => setChartTab("broker")}
                >
                  Broker Analysis
                </button>
                <button
                  className={`rounded px-3 py-1 ${chartTab === "tradingview" ? "bg-sky-500/20 text-sky-300" : "text-slate-400"}`}
                  onClick={() => setChartTab("tradingview")}
                >
                  TradingView
                </button>
              </div>
            </div>
            {chartTab === "broker" ? (
              <BrokerAnalysisPanel detail={brokerDetail} periodDays={brokerDays} />
            ) : (
              <div className="w-full" style={{ height: 500 }}>
                <iframe
                  src={`https://s.tradingview.com/widgetembed/?frameElementId=tradingview_${ticker}&symbol=IDX%3A${ticker}&interval=D&hidesidetoolbar=1&hidetoptoolbar=1&symboledit=0&saveimage=0&theme=dark&style=1&timezone=Asia%2FJakarta&withdateranges=0&studies=EMA%3A20%7CEMA%3A50%7CRSI%7CVolume&showpopupbutton=0&studies_overrides=%7B%7D&overrides=%7B%7D&enabled_features=%5B%5D&disabled_features=%5B%5D&locale=en`}
                  style={{ width: "100%", height: "100%", border: "none" }}
                  title="TradingView Chart"
                />
              </div>
            )}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="card"><h2 className="font-semibold mb-3">Score Timeline</h2><ScoreTimeline data={data.scores} /></div>
            <div className="card"><h2 className="font-semibold mb-3">Sub-Score Radar</h2><ScoreRadar data={data.scores} /></div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="card"><h2 className="font-semibold mb-3">Harmonic Pattern</h2><HarmonicPanel data={data.technical} /></div>
            <div className="card"><h2 className="font-semibold mb-3">Elliott Wave</h2><ElliottPanel data={data.technical} /></div>
          </div>
          <div className="card"><h2 className="font-semibold mb-3">Bandarmology</h2><BandarPanel data={data.bandarmology} /></div>
          <div className="grid grid-cols-2 gap-4">
            <div className="card"><h2 className="font-semibold mb-3">Foreign Flow</h2><ForeignFlowPanel data={data.foreign_flow} /></div>
            <div className="card"><h2 className="font-semibold mb-3">Top Brokers</h2><TopBrokerPanel data={data.brokers} periodDays={brokerDays} /></div>
          </div>
          <div className="card">
            <h2 className="font-semibold mb-3">Broker Conviction</h2>
            <BrokerConvictionPanel detail={brokerDetail} />
          </div>
        </div>
      )}
    </div>
  );
}
