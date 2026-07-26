"use client";
import { createChart, CrosshairMode } from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";
import { ComposedChart, Line, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, Radar, CartesianGrid, Cell, ReferenceLine } from "recharts";

export function CandlestickChart({ data, prices }: { data: any[]; prices: any[] }) {
  if (!data?.length) return <p className="text-slate-400 text-sm">No price data.</p>;
  // Extract trend structure EMA values
  const trendMap: Record<string, any> = {};
  for (const t of data) {
    if (t.method === "trend_structure" && t.payload) {
      trendMap[t.date] = {
        ema20: t.payload.ema20,
        ema50: t.payload.ema50,
        structure: t.payload.structure,
      };
    }
  }
  const rows = prices.map((p) => {
    const d = p.date.slice(5);
    const trend = trendMap[p.date] || {};
    return { date: d, close: p.close, volume: p.volume, ema20: trend.ema20, ema50: trend.ema50, structure: trend.structure };
  });
  if (rows.length >= 20) {
    for (let i = 19; i < rows.length; i++) {
      let sum = 0;
      for (let j = i - 19; j <= i; j++) sum += rows[j].volume || 0;
      (rows[i] as any).volMa20 = sum / 20;
    }
  }
  return (
    <div>
      <div className="flex gap-4 text-xs text-slate-400 mb-2 flex-wrap">
        <span><span className="inline-block w-3 h-0.5 bg-[#60a5fa] align-middle mr-1" style={{borderTop:"2.5px solid #60a5fa"}}></span>Close</span>
        <span><span className="inline-block w-3 h-0.5 bg-[#f59e0b] align-middle mr-1" style={{borderTop:"1.5px solid #f59e0b"}}></span>EMA20</span>
        <span><span className="inline-block w-3 h-0.5 bg-[#a78bfa] align-middle mr-1" style={{borderTop:"1.5px solid #a78bfa"}}></span>EMA50</span>
        <span><span className="inline-block w-2 h-2 bg-[#1e3a5f] align-middle mr-1 opacity-40"></span>Volume</span>
        <span><span className="inline-block w-3 h-0.5 bg-[#f87171] align-middle mr-1" style={{borderTop:"1px dashed #f87171"}}></span>Vol MA20</span>
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={rows}>
          <CartesianGrid stroke="#1e293b" />
          <XAxis dataKey="date" stroke="#64748b" fontSize={11} />
          <YAxis yAxisId="price" stroke="#64748b" fontSize={11} domain={["auto", "auto"]} />
          <YAxis yAxisId="volume" orientation="right" stroke="#64748b" fontSize={10} tickFormatter={(v:number) => (v/1e6).toFixed(0)+"M"} />
          <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", fontSize: 12 }} />
          <Line yAxisId="price" dataKey="close" stroke="#60a5fa" dot={false} strokeWidth={2.5} />
          <Line yAxisId="price" dataKey="ema20" stroke="#f59e0b" dot={false} strokeWidth={1.5} connectNulls />
          <Line yAxisId="price" dataKey="ema50" stroke="#a78bfa" dot={false} strokeWidth={1.5} connectNulls />
          <Bar yAxisId="volume" dataKey="volume" fill="#1e3a5f" barSize={3} opacity={0.4} />
          <Line yAxisId="volume" dataKey="volMa20" stroke="#f87171" dot={false} strokeWidth={1} strokeDasharray="4 2" connectNulls />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="text-xs text-slate-500 mt-1">EMA20 (kuning) & EMA50 (ungu) dari Trend Structure</div>
    </div>
  );
}

export function ScoreTimeline({ data }: { data: any[] }) {
  if (!data?.length) return <p className="text-slate-400 text-sm">No scores.</p>;
  const rows = data.map((s) => ({ date: s.date.slice(5), composite: s.composite }));
  return (
    <div>
      <div className="text-xs text-slate-400 mb-2 space-y-1">
        <div>Skor gabungan teknikal + bandar + foreign flow + regime.</div>
        <div className="flex gap-3 flex-wrap">
          <span className="text-emerald-400">70-100</span> Bullish (kuat beli)
          <span className="text-amber-400">40-70</span> Netral (tahan/tunggu)
          <span className="text-red-400">0-40</span> Bearish (jual/hindari)
        </div>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart data={rows}>
          <CartesianGrid stroke="#1e293b" />
          <XAxis dataKey="date" stroke="#64748b" fontSize={10} />
          <YAxis domain={[0, 100]} stroke="#64748b" fontSize={10} />
          <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #1e293b" }} />
          <ReferenceLine y={70} stroke="#34d399" strokeDasharray="4 2" strokeWidth={1} />
          <ReferenceLine y={40} stroke="#f87171" strokeDasharray="4 2" strokeWidth={1} />
          <Line dataKey="composite" stroke="#facc15" dot={false} strokeWidth={2} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ScoreRadar({ data }: { data: any[] }) {
  if (!data?.length) return <p className="text-slate-400 text-sm">No scores.</p>;
  const latest = data[data.length - 1];
  const sub = latest.sub_scores || {};
  const rows = Object.entries(sub).map(([k, v]: any) => ({ method: k.replace("tech:", "T:").replace("bandar:", "B:").replace("foreign_flow", "Asing").replace("regime", "Rezim"), score: Math.round(v) }));
  return (
    <div>
      <div className="text-xs text-slate-400 mb-1">Sub-score per komponen. T = teknikal, B = bandarmology</div>
      <ResponsiveContainer width="100%" height={220}>
        <RadarChart data={rows}>
          <PolarGrid stroke="#1e293b" />
          <PolarAngleAxis dataKey="method" stroke="#94a3b8" fontSize={10} />
          <Radar dataKey="score" stroke="#818cf8" fill="#818cf8" fillOpacity={0.4} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function BandarPanel({ data }: { data: any[] }) {
  if (!data?.length) return <p className="text-slate-400 text-sm">No bandarmology data.</p>;
  const byDate: Record<string, any> = {};
  for (const r of data) {
    byDate[r.date] = byDate[r.date] || { date: r.date.slice(5) };
    byDate[r.date][r.label] = r.detected ? 1 : 0;
  }
  const rows = Object.values(byDate).slice(-90);
  const labels = ["hidden_accumulation","silent_accumulation","shakeout","absorption","bandar_positioning","consistency"];
  const colors = ["#34d399","#60a5fa","#f59e0b","#f472b6","#a78bfa","#22d3ee"];
  const names = ["Hidden Acc","Silent Acc","Shakeout","Absorption","Positioning","Consistency"];
  return (
    <div>
      <div className="flex gap-3 text-xs text-slate-400 mb-2 flex-wrap">
        {labels.map((l, i) => (
          <span key={l}><span className="inline-block w-2 h-2 rounded-sm mr-1 align-middle" style={{backgroundColor:colors[i]}}></span>{names[i]}</span>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <ComposedChart data={rows}>
          <CartesianGrid stroke="#1e293b" />
          <XAxis dataKey="date" stroke="#64748b" fontSize={10} />
          <YAxis domain={[0, 1]} tick={{fontSize:10}} stroke="#64748b" ticks={[0, 1]} tickFormatter={(v:number) => v?"Ada":"-"} />
          <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #1e293b" }} formatter={(v:any)=>v?"Terdeteksi":"-"}/>
          {labels.map((l, i) => (
            <Bar key={l} dataKey={l} stackId="a" fill={colors[i]} />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ForeignFlowPanel({ data }: { data: any[] }) {
  if (!data?.length) return <p className="text-slate-400 text-sm">No foreign flow data.</p>;
  const rows = data.map((d) => ({ date: d.date.slice(5), net: d.net_foreign }));
  const latest = data[data.length - 1];
  const fmtPct = (v?: number | null) => v != null ? `${v.toFixed(4)}%` : "-";
  return (
    <div>
      <div className="text-xs text-slate-400 mb-1 flex flex-wrap gap-3">
        <span><span className="text-emerald-400">Hijau</span> = asing beli bersih</span>
        <span><span className="text-red-400">Merah</span> = asing jual bersih</span>
        {latest && (
          <span className="text-slate-500">Latest %MCap: <span className={latest.net_foreign >= 0 ? "text-emerald-400" : "text-red-400"}>{fmtPct(latest.pct_market_cap)}</span> %ADV: <span className={latest.net_foreign >= 0 ? "text-emerald-400" : "text-red-400"}>{fmtPct(latest.pct_avg_daily_value)}</span></span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={180}>
        <ComposedChart data={rows}>
          <CartesianGrid stroke="#1e293b" />
          <XAxis dataKey="date" stroke="#64748b" fontSize={10} />
          <YAxis stroke="#64748b" fontSize={10} tickFormatter={(v:number) => (v/1e9).toFixed(0)+"B"} />
          <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #1e293b" }} formatter={(v:any)=>v?(v/1e9).toFixed(2)+" B":"-"}/>
          <Bar dataKey="net" barSize={4}>
            {rows.map((r, i) => (
              <Cell key={i} fill={(r.net || 0) >= 0 ? "#34d399" : "#f87171"} />
            ))}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function HarmonicPanel({ data }: { data: any[] }) {
  const latest = data.filter((t) => t.method === "harmonic" && t.payload?.pattern).pop();
  if (!latest) return <p className="text-slate-400 text-sm">No harmonic pattern detected.</p>;
  const p = latest.payload;
  return (
    <div>
      <div className="text-xs text-slate-400 mb-2">Harmonic Pattern (latest detected)</div>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div><span className="text-slate-400">Pattern:</span> <span className="font-mono text-indigo-400">{p.pattern || "none"}</span></div>
        <div><span className="text-slate-400">Date:</span> <span className="font-mono">{latest.date}</span></div>
        {p.ratios && (
          <div className="col-span-2">
            <div className="text-slate-400 text-xs mb-1">Fibonacci Ratios:</div>
            <div className="grid grid-cols-2 gap-1 font-mono text-xs">
              {Object.entries(p.ratios).map(([k, v]) => (
                <div key={k}>{k.toUpperCase()}: {(v as number).toFixed(3)}</div>
              ))}
            </div>
          </div>
        )}
        {p.pivots && (
          <div className="col-span-2">
            <div className="text-slate-400 text-xs mb-1">Pivot Points:</div>
            <div className="flex gap-2 font-mono text-xs">
              {(p.pivots as any[]).map((pt: any, i: number) => (
                <span key={i} className="bg-slate-800 px-1 rounded">{pt.type}{pt.price?.toFixed(0)}</span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function ElliottPanel({ data }: { data: any[] }) {
  const latest = data.filter((t) => t.method === "elliott_wave" && t.payload?.label).pop();
  if (!latest) return <p className="text-slate-400 text-sm">Belum ada data Elliott Wave.</p>;
  const p = latest.payload;
  const isImpulse = p.label?.includes("impulse");
  const isUp = p.label?.includes("up");
  const pivots = p.pivots || [];
  const prices = pivots.map((x:any) => x.price);
  const types = pivots.map((x:any) => x.type);

  let explanation = "";
  let action = "";
  if (isImpulse && isUp && pivots.length >= 5) {
    explanation = "Impulse naik 5-gelombang terdeteksi. Gelombang 1-2-3-4-5 bullish. Setelah wave 5, biasanya koreksi A-B-C turun.";
    action = prices[prices.length-1] > prices[prices.length-2] ? "Wave 5 sedang naik, target di atas" : "Wave 5 mungkin sudah selesai, waspada koreksi";
  } else if (isImpulse && !isUp && pivots.length >= 5) {
    explanation = "Impulse turun 5-gelombang terdeteksi. Gelombang 1-2-3-4-5 bearish. Setelah wave 5, biasanya reversal naik.";
    action = "Wave 5 turun, pantau reversal di support terdekat";
  } else if (p.label?.includes("corrective")) {
    explanation = "Pola korektif A-B-C terdeteksi. Pasar sedang konsolidasi setelah tren sebelumnya.";
    action = "Tunggu breakout dari pola korektif untuk entry";
  } else {
    explanation = isUp ? "Struktur naik terdeteksi." : "Struktur turun terdeteksi.";
    action = "Pantau konfirmasi sinyal teknikal lain";
  }

  return (
    <div>
      <div className="text-xs text-slate-400 mb-2">Elliott Wave — {latest.date}</div>
      <div className="space-y-3 text-sm">
        <div className={`p-2 rounded text-xs leading-relaxed ${isUp ? "bg-emerald-950/40 text-emerald-300 border border-emerald-900" : "bg-red-950/40 text-red-300 border border-red-900"}`}>
          {explanation}
        </div>
        {pivots.length >= 2 && (
          <div className="space-y-1">
            <div className="text-slate-400 text-xs">Pivot Points:</div>
            <div className="flex items-center gap-1 font-mono text-xs flex-wrap">
              {pivots.map((pt: any, i: number) => (
                <span key={i}>
                  <span className={`${pt.type==="H"?"text-red-400":"text-emerald-400"}`}>{pt.type}{pt.price?.toFixed(0)}</span>
                  {i < pivots.length-1 && <span className="text-slate-600 mx-0.5">→</span>}
                </span>
              ))}
            </div>
            <div className="flex gap-1 mt-1">
              {pivots.map((pt: any, i: number) => {
                const next = pivots[i+1];
                if (!next) return null;
                const up = next.price > pt.price;
                const label = isImpulse ? `W${i+1}` : ["A","B","C"][i] || "";
                return (
                  <span key={i} className={`text-xs px-1.5 py-0.5 rounded font-mono ${up ? "bg-emerald-900/50 text-emerald-300" : "bg-red-900/50 text-red-300"}`}>
                    {label} {up ? "↑" : "↓"}
                  </span>
                );
              })}
            </div>
          </div>
        )}
        <div className="p-2 rounded bg-slate-800/50 border border-slate-700 text-xs text-amber-300">
          {action}
        </div>
      </div>
    </div>
  );
}

export function TopBrokerPanel({ data, periodDays }: { data: any[]; periodDays?: number }) {
  const [selected, setSelected] = useState<any>(null);
  if (!data?.length) return <p className="text-slate-400 text-sm">No broker data.</p>;
  const fmt = (v: number) => {
    if (Math.abs(v) >= 1e12) return (v / 1e12).toFixed(1) + "T";
    if (Math.abs(v) >= 1e9) return (v / 1e9).toFixed(1) + "B";
    if (Math.abs(v) >= 1e6) return (v / 1e6).toFixed(0) + "M";
    return v.toFixed(0);
  };
  const fmtPct = (v: number | null | undefined) => {
    if (v === null || v === undefined) return "-";
    return `${v.toFixed(4)}%`;
  };
  const sorted = [...data].sort((a, b) => {
    const pa = a.pct_market_cap ?? 0;
    const pb = b.pct_market_cap ?? 0;
    if (pa !== pb) return pb - pa;
    return b.net - a.net;
  });
  const first = sorted[0] || {};
  const tradingDays = first.trading_days || Math.max(...sorted.map((b) => b.days || 0), 0);
  const periodLabel = (first.period_days || periodDays || 30) <= 7 ? "1 Minggu" : "1 Bulan";
  const dateRange = first.start_date && first.end_date ? `${first.start_date} s/d ${first.end_date}` : "";
  return (
    <div>
      <div className="text-xs text-slate-400 mb-2">
        Top 15 Broker — Akumulasi {periodLabel} ({tradingDays} hari bursa{dateRange ? `, ${dateRange}` : ""}, diurutkan % Market Cap)
      </div>
      {selected && (
        <div className="mb-2 p-2 rounded bg-slate-800 border border-slate-700 text-xs space-y-1">
          <div className="flex justify-between">
            <span className="font-mono font-bold text-indigo-400">{selected.broker}</span>
            <button className="text-slate-500 hover:text-white" onClick={() => setSelected(null)}>✕</button>
          </div>
          <div className="grid grid-cols-2 gap-1">
            <div>Buy: <span className="text-emerald-400">{fmt(selected.buy)}</span></div>
            <div>Sell: <span className="text-red-400">{fmt(selected.sell)}</span></div>
            <div>Net: <span className={selected.net >= 0 ? "text-emerald-400" : "text-red-400"}>{fmt(selected.net)}</span></div>
            <div>Aktif: {selected.days || "-"} hari</div>
            <div>Buy freq: <span className="text-slate-200">{selected.buy_freq ?? "-"}</span></div>
            <div>Sell freq: <span className="text-slate-200">{selected.sell_freq ?? "-"}</span></div>
            <div className="col-span-2">Net/hari: <span className={selected.net >= 0 ? "text-emerald-400" : "text-red-400"}>{fmt((selected.net || 0) / Math.max(selected.days || 1, 1))}</span></div>
            <div className="col-span-2">% Market Cap: <span className={selected.net >= 0 ? "text-emerald-400" : "text-red-400"}>{fmtPct(selected.pct_market_cap)}</span></div>
            <div className="col-span-2">% Avg Daily Value: <span className={selected.net >= 0 ? "text-emerald-400" : "text-red-400"}>{fmtPct(selected.pct_avg_daily_value)}</span></div>
            <div className="col-span-2 mt-1 text-slate-400">
              Broker {selected.broker} {selected.net >= 0 ? "membeli bersih" : "menjual bersih"} senilai {fmt(Math.abs(selected.net))} ({fmtPct(selected.pct_market_cap)} dari market cap) selama {selected.days || "-"} hari terakhir.
            </div>
            <div className="col-span-2 text-slate-500">
              Frequency berasal dari field `freq` Stockbit. Average price dan volume per broker belum ditampilkan karena belum ada field sumber yang tervalidasi konsisten.
            </div>
          </div>
        </div>
      )}
      <div className="overflow-x-auto max-h-64 overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-slate-900">
            <tr className="text-slate-400 text-xs">
              <th className="text-left">#</th><th className="text-left">Broker</th><th className="text-right">Net</th><th className="text-right">%MCap</th><th className="text-right">%ADV</th><th className="text-right">Hari</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((b, i) => (
              <tr key={i} className={`border-t border-slate-800 text-xs hover:bg-slate-800/50 cursor-pointer ${selected?.broker === b.broker ? "bg-slate-800" : ""}`} onClick={() => setSelected(selected?.broker === b.broker ? null : b)}>
                <td className="py-1 text-slate-500">{i + 1}</td>
                <td className="font-mono text-indigo-400">{b.broker}</td>
                <td className={`text-right font-mono ${b.net >= 0 ? "text-emerald-400" : "text-red-400"}`}>{fmt(b.net)}</td>
                <td className={`text-right ${b.net >= 0 ? "text-emerald-400/80" : "text-red-400/80"}`}>{fmtPct(b.pct_market_cap)}</td>
                <td className={`text-right ${b.net >= 0 ? "text-emerald-400/80" : "text-red-400/80"}`}>{fmtPct(b.pct_avg_daily_value)}</td>
                <td className="text-right text-slate-500">{b.days || "-"}d</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function BrokerConvictionPanel({ detail }: { detail: any }) {
  if (!detail?.broker_conviction) return <p className="text-slate-400 text-sm">No broker conviction detail.</p>;

  const conviction = detail.broker_conviction || {};
  const flowQuality = detail.flow_quality || {};
  const entry = detail.entry_readiness || {};
  const oneWeek = detail.one_week || {};
  const oneMonth = detail.one_month || {};
  const comparison = detail.comparison || {};
  const components = conviction.components || {};

  const fmtPct = (v: number | null | undefined) => {
    if (v === null || v === undefined) return "-";
    return `${v.toFixed(4)}%`;
  };
  const fmtNum = (v: number | null | undefined, digits = 1) => {
    if (v === null || v === undefined) return "-";
    return v.toFixed(digits);
  };
  const fmtMoney = (v: number | null | undefined) => {
    if (v === null || v === undefined) return "-";
    const n = Math.abs(v);
    if (n >= 1e12) return `${(v / 1e12).toFixed(1)}T`;
    if (n >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
    if (n >= 1e6) return `${(v / 1e6).toFixed(0)}M`;
    return v.toFixed(0);
  };
  const contributionMeta = [
    {
      key: "magnitude",
      label: "Magnitude",
      color: "bg-amber-500",
      weight: 20,
      hint: "Membandingkan besar net broker terhadap market cap dan likuiditas normal saham.",
    },
    {
      key: "persistence",
      label: "Persistence",
      color: "bg-emerald-500",
      weight: 20,
      hint: "Seberapa sering broker utama net buy pada window yang sama.",
    },
    {
      key: "recency",
      label: "Recency",
      color: "bg-sky-500",
      weight: 15,
      hint: "Mengukur kedekatan sesi net buy terakhir dengan tanggal evaluasi.",
    },
    {
      key: "acceleration",
      label: "Acceleration",
      color: "bg-indigo-500",
      weight: 15,
      hint: "Membandingkan laju net buy 5 sesi terbaru versus blok sesi sebelumnya.",
    },
    {
      key: "retention",
      label: "Retention",
      color: "bg-fuchsia-500",
      weight: 10,
      hint: "Apakah posisi kumulatif broker masih terjaga dekat puncaknya atau sudah dibuang lagi.",
    },
    {
      key: "cluster",
      label: "Cluster",
      color: "bg-orange-500",
      weight: 10,
      hint: "Konfirmasi apakah top-3 buyer bergerak bersama, bukan hanya satu broker tunggal.",
    },
    {
      key: "purity",
      label: "Purity",
      color: "bg-cyan-500",
      weight: 5,
      hint: "Membedakan akumulasi satu arah dari broker yang bolak-balik buy/sell.",
    },
    {
      key: "quality",
      label: "Quality",
      color: "bg-lime-500",
      weight: 5,
      hint: "Penalty untuk flow yang terlalu berimbang buy-sell atau coverage kualitas data yang lemah.",
    },
  ] as const;
  const scoreBar = (
    label: string,
    value: number | null | undefined,
    color: string,
    weight: number,
    hint: string,
  ) => {
    const clipped = Math.max(0, Math.min(100, value || 0));
    const weightedContribution = ((value || 0) * weight) / 100;
    return (
      <div key={label} className="space-y-1">
        <div className="flex items-center justify-between gap-3 text-xs">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span title={hint} className="cursor-help border-b border-dotted border-slate-600 text-slate-300">
                {label}
              </span>
              <span className="rounded border border-slate-700 bg-slate-950 px-1.5 py-0.5 text-[10px] text-slate-500">
                {weight}%
              </span>
            </div>
            <div className="truncate text-[11px] text-slate-500">{hint}</div>
          </div>
          <div className="text-right">
            <div className="font-mono text-white">{fmtNum(value, 1)}</div>
            <div className="font-mono text-[11px] text-slate-500">+{fmtNum(weightedContribution, 1)} pts</div>
          </div>
        </div>
        <div className="h-2 rounded bg-slate-800 overflow-hidden">
          <div className={`h-full ${color}`} style={{ width: `${clipped}%` }} />
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3 text-sm">
        <div className="rounded border border-slate-800 bg-slate-900/70 p-3">
          <div className="text-xs text-slate-400 mb-1">Broker Conviction</div>
          <div className="flex items-end gap-2">
            <span className="text-3xl font-mono text-amber-300">{fmtNum(conviction.score, 1)}</span>
            <span className="text-sm text-emerald-300">{conviction.label || "-"}</span>
          </div>
          <div className="mt-2 text-xs text-slate-400">Status: <span className="text-slate-200">{conviction.status || "-"}</span></div>
          <div className="mt-1 text-xs text-slate-500">Combined Rank: <span className="font-mono text-sky-300">{fmtNum(conviction.combined_rank_score, 1)}</span></div>
        </div>
        <div className="rounded border border-slate-800 bg-slate-900/70 p-3">
          <div className="text-xs text-slate-400 mb-1">Entry Readiness</div>
          <div className="flex items-end gap-2">
            <span className="text-3xl font-mono text-sky-300">{fmtNum(entry.score, 1)}</span>
            <span className="text-sm text-slate-300">{entry.phase || "-"}</span>
          </div>
          <div className="mt-2 text-xs text-slate-400">Composite: <span className="font-mono text-white">{fmtNum(entry.composite, 1)}</span></div>
          <div className="mt-1 text-xs text-slate-500">{(entry.tags || []).join(", ") || "no special tags"}</div>
        </div>
        <div className="rounded border border-slate-800 bg-slate-900/70 p-3">
          <div className="text-xs text-slate-400 mb-1">Flow Quality</div>
          <div className="flex items-end gap-2">
            <span className="text-3xl font-mono text-cyan-300">{fmtNum(flowQuality.score, 1)}</span>
            <span className="text-sm text-cyan-200">{flowQuality.label || "-"}</span>
          </div>
          <div className="mt-2 text-xs text-slate-400">Net / trade: <span className="font-mono text-white">{fmtMoney(flowQuality.net_per_trade)}</span></div>
          <div className="mt-1 text-xs text-slate-500">
            {(flowQuality.retail_distribution_risk ? "retail_distribution_risk, " : "")}
            {(flowQuality.high_freq_low_value ? "high_freq_low_value, " : "")}
            {(flowQuality.low_freq_high_value ? "low_freq_high_value" : "") || "no extra flow flags"}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2 rounded border border-slate-800 bg-slate-900/70 p-3">
          <div className="space-y-1">
            <div className="text-xs text-slate-400">Contribution</div>
            <div className="text-[11px] text-slate-500">
              Bar menunjukkan skor mentah 0-100 per komponen. Angka kecil di kanan menunjukkan kontribusi berbobot terhadap conviction final.
            </div>
          </div>
          {contributionMeta.map((item) =>
            scoreBar(item.label, components[item.key], item.color, item.weight, item.hint),
          )}
          <div className="mt-3 rounded border border-slate-800 bg-slate-950/80 p-3 text-[11px] text-slate-400">
            <div className="mb-2 text-xs text-slate-300">Cara baca cepat</div>
            <div><span className="text-slate-200">Sehat:</span> magnitude + persistence + retention + cluster sama-sama tinggi.</div>
            <div><span className="text-slate-200">Masih aktif:</span> recency + acceleration tinggi, artinya akumulasi masih berjalan dekat tanggal sekarang.</div>
            <div><span className="text-slate-200">Spike saja:</span> magnitude tinggi tapi persistence atau retention rendah, jadi dorongan besar belum tentu bertahan.</div>
            <div><span className="text-slate-200">Kurang rapi:</span> quality rendah atau purity rendah, flow cenderung noisy / bolak-balik.</div>
            <div><span className="text-slate-200">Perlu konfirmasi:</span> cluster rendah berarti akumulasi belum didukung broker buyer lain.</div>
          </div>
        </div>
        <div className="rounded border border-slate-800 bg-slate-900/70 p-3">
          <div className="text-xs text-slate-400 mb-2">1W vs 1M</div>
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div className="text-slate-500"></div>
            <div className="text-slate-400 font-medium">1W</div>
            <div className="text-slate-400 font-medium">1M</div>
            <div className="text-slate-500">Label</div>
            <div className="text-emerald-300">{oneWeek.broker_conviction_label || "-"}</div>
            <div className="text-emerald-300">{oneMonth.broker_conviction_label || "-"}</div>
            <div className="text-slate-500">Score</div>
            <div className="font-mono">{fmtNum(oneWeek.broker_conviction_score, 1)}</div>
            <div className="font-mono">{fmtNum(oneMonth.broker_conviction_score, 1)}</div>
            <div className="text-slate-500">Net</div>
            <div className="font-mono">{fmtMoney(oneWeek.net)}</div>
            <div className="font-mono">{fmtMoney(oneMonth.net)}</div>
            <div className="text-slate-500">%MCap</div>
            <div>{fmtPct(oneWeek.pct_market_cap)}</div>
            <div>{fmtPct(oneMonth.pct_market_cap)}</div>
            <div className="text-slate-500">Days ADV</div>
            <div>{fmtNum(oneWeek.days_of_adv, 2)}</div>
            <div>{fmtNum(oneMonth.days_of_adv, 2)}</div>
            <div className="text-slate-500">Pos Ratio</div>
            <div>{fmtNum((oneWeek.positive_ratio || 0) * 100, 1)}%</div>
            <div>{fmtNum((oneMonth.positive_ratio || 0) * 100, 1)}%</div>
            <div className="text-slate-500">Last Buy</div>
            <div>{oneWeek.last_buy_date || "-"}</div>
            <div>{oneMonth.last_buy_date || "-"}</div>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-400">
            <div>Conviction delta: <span className="font-mono text-white">{fmtNum(comparison.conviction_delta, 1)}</span></div>
            <div>Acceleration delta: <span className="font-mono text-white">{fmtNum(comparison.acceleration_delta, 1)}</span></div>
            <div>Positive ratio delta: <span className="font-mono text-white">{fmtNum((comparison.positive_ratio_delta || 0) * 100, 1)}%</span></div>
            <div>Recency delta: <span className="font-mono text-white">{fmtNum(comparison.recency_delta, 0)}</span></div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function BrokerAnalysisPanel({ detail, periodDays }: { detail: any; periodDays: number }) {
  const periodKey = periodDays <= 7 ? "one_week" : "one_month";
  const periodDetail = useMemo(() => detail?.[periodKey] || {}, [detail, periodKey]);
  const heatmapRows = periodDetail.chart?.heatmap_rows || [];
  const defaultBroker = heatmapRows[0]?.broker || periodDetail.top_broker || null;
  const [selectedBroker, setSelectedBroker] = useState<string | null>(defaultBroker);
  const priceRef = useRef<HTMLDivElement | null>(null);
  const flowRef = useRef<HTMLDivElement | null>(null);
  const cumulativeRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setSelectedBroker(defaultBroker);
  }, [defaultBroker, periodKey]);

  useEffect(() => {
    const priceEl = priceRef.current;
    const flowEl = flowRef.current;
    const cumulativeEl = cumulativeRef.current;
    if (!priceEl || !flowEl || !cumulativeEl) return;

    const chart = periodDetail.chart || {};
    const priceSeries = chart.price_series || [];
    const brokerSeriesMap = chart.broker_daily_series || {};
    const selectedSeries = brokerSeriesMap[selectedBroker || ""] || chart.selected_broker_daily || [];
    const clusterSeries = chart.cluster_daily || [];
    if (!priceSeries.length) return;

    const commonOptions = {
      width: priceEl.clientWidth || 800,
      layout: { background: { color: "#020617" }, textColor: "#94a3b8" },
      grid: { vertLines: { color: "#0f172a" }, horzLines: { color: "#0f172a" } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#1e293b" },
      timeScale: { borderColor: "#1e293b", timeVisible: true, secondsVisible: false },
    };

    const priceChart = createChart(priceEl, { ...commonOptions, height: 280 });
    const flowChart = createChart(flowEl, { ...commonOptions, height: 170 });
    const cumulativeChart = createChart(cumulativeEl, { ...commonOptions, height: 170 });

    const candle = priceChart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });
    candle.setData(
      priceSeries
        .filter((p: any) => p.open != null && p.high != null && p.low != null && p.close != null)
        .map((p: any) => ({
          time: p.date,
          open: p.open,
          high: p.high,
          low: p.low,
          close: p.close,
        }))
    );

    const volume = priceChart.addHistogramSeries({
      color: "#1d4ed8",
      priceFormat: { type: "volume" },
      priceScaleId: "",
    });
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.75, bottom: 0 } });
    volume.setData(
      priceSeries
        .filter((p: any) => p.volume != null)
        .map((p: any) => ({
          time: p.date,
          value: p.volume,
          color: (p.close || 0) >= (p.open || 0) ? "rgba(34,197,94,0.35)" : "rgba(239,68,68,0.35)",
        }))
    );

    const flowHistogram = flowChart.addHistogramSeries({
      priceLineVisible: false,
      base: 0,
    });
    flowHistogram.setData(
      selectedSeries.map((p: any) => ({
        time: p.date,
        value: p.net_value ?? 0,
        color: p.net_value == null ? "rgba(100,116,139,0.25)" : p.net_value >= 0 ? "rgba(34,197,94,0.8)" : "rgba(239,68,68,0.8)",
      }))
    );

    const flowCluster = flowChart.addLineSeries({
      color: "#f59e0b",
      lineWidth: 2,
      priceLineVisible: false,
    });
    flowCluster.setData(
      clusterSeries
        .filter((p: any) => p.net_value != null)
        .map((p: any) => ({ time: p.date, value: p.net_value }))
    );

    const cumulativeSelected = cumulativeChart.addLineSeries({
      color: "#60a5fa",
      lineWidth: 2,
      priceLineVisible: false,
    });
    cumulativeSelected.setData(
      selectedSeries
        .filter((p: any) => p.cumulative_net != null)
        .map((p: any) => ({ time: p.date, value: p.cumulative_net }))
    );

    const cumulativeCluster = cumulativeChart.addLineSeries({
      color: "#f59e0b",
      lineWidth: 2,
      priceLineVisible: false,
    });
    cumulativeCluster.setData(
      clusterSeries
        .filter((p: any) => p.cumulative_net != null)
        .map((p: any) => ({ time: p.date, value: p.cumulative_net }))
    );

    const charts = [priceChart, flowChart, cumulativeChart];
    let syncing = false;
    for (const sourceChart of charts) {
      sourceChart.timeScale().subscribeVisibleTimeRangeChange((range) => {
        if (!range || syncing) return;
        syncing = true;
        for (const targetChart of charts) {
          if (targetChart !== sourceChart) {
            targetChart.timeScale().setVisibleRange(range);
          }
        }
        syncing = false;
      });
    }

    priceChart.timeScale().fitContent();
    flowChart.timeScale().fitContent();
    cumulativeChart.timeScale().fitContent();

    const resizeObserver = new ResizeObserver(() => {
      const width = priceEl.clientWidth || 800;
      priceChart.applyOptions({ width });
      flowChart.applyOptions({ width });
      cumulativeChart.applyOptions({ width });
    });
    resizeObserver.observe(priceEl);

    return () => {
      resizeObserver.disconnect();
      priceChart.remove();
      flowChart.remove();
      cumulativeChart.remove();
    };
  }, [periodDetail, selectedBroker]);

  if (!detail?.broker_conviction || !periodDetail.chart?.price_series?.length) {
    return <p className="text-slate-400 text-sm">No broker analysis data.</p>;
  }

  const maxAbs = Math.max(
    1,
    ...heatmapRows.flatMap((row: any) => row.cells.map((cell: any) => Math.abs(cell.net_value || 0))),
  );
  const selectedSummary = heatmapRows.find((row: any) => row.broker === selectedBroker) || heatmapRows[0];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 text-xs text-slate-400">
        <div>Period: <span className="text-white">{periodDetail.period || "-"}</span> ({periodDetail.date_from || "-"} s/d {periodDetail.date_to || "-"})</div>
        <div>Coverage: <span className="text-white">{((periodDetail.coverage_ratio || 0) * 100).toFixed(1)}%</span></div>
        <div>Selected Broker: <span className="font-mono text-sky-300">{selectedBroker || "-"}</span></div>
        <div>Cluster: <span className="font-mono text-amber-300">{(periodDetail.cluster_brokers || []).join(", ") || "-"}</span></div>
      </div>

      <div className="rounded border border-slate-800 bg-slate-950/70 p-3">
        <div className="mb-2 flex flex-wrap gap-4 text-xs text-slate-400">
          <span className="text-white">Price</span>
          <span className="text-sky-300">Selected broker cumulative</span>
          <span className="text-amber-300">Top-3 cluster</span>
        </div>
        <div ref={priceRef} className="w-full" />
        <div className="mt-3 text-xs text-slate-400">Broker daily flow</div>
        <div ref={flowRef} className="w-full" />
        <div className="mt-3 text-xs text-slate-400">Cumulative flow</div>
        <div className="mt-1 rounded border border-slate-800 bg-slate-900/70 p-2 text-xs text-slate-400">
          <div className="flex flex-wrap gap-4">
            <span><span className="text-sky-300">Biru</span> = akumulasi net buy/net sell broker yang dipilih</span>
            <span><span className="text-amber-300">Kuning</span> = akumulasi gabungan 3 broker teratas</span>
          </div>
          <div className="mt-1 flex flex-wrap gap-4 text-slate-500">
            <span>Naik = akumulasi makin kuat</span>
            <span>Turun = distribusi / net sell makin besar</span>
            <span>Datar = tambahan flow kecil atau stagnan</span>
          </div>
          <div className="mt-1 text-slate-500">
            Jika biru dan kuning naik bareng, broker pilihan searah dengan cluster. Jika biru naik tapi kuning lemah, akumulasi belum didukung broker besar lain.
          </div>
        </div>
        <div ref={cumulativeRef} className="w-full" />
      </div>

      <div className="rounded border border-slate-800 bg-slate-900/70 p-3">
        <div className="mb-2 flex items-center justify-between">
          <div className="text-xs text-slate-400">Broker Heatmap Top-5</div>
          {selectedSummary && (
            <div className="text-xs text-slate-500">
              {selectedSummary.broker}: net {selectedSummary.total_net?.toFixed?.(0) ?? "-"}, retention {((selectedSummary.retention || 0) * 100).toFixed(1)}%
            </div>
          )}
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full border-separate border-spacing-1 text-xs">
            <thead>
              <tr className="text-slate-500">
                <th className="sticky left-0 bg-slate-900 px-2 py-1 text-left">Broker</th>
                {(heatmapRows[0]?.cells || []).map((cell: any) => (
                  <th key={cell.date} className="px-1 py-1 font-mono">{cell.date.slice(5)}</th>
                ))}
                <th className="px-2 py-1">Net</th>
                <th className="px-2 py-1">Pos</th>
              </tr>
            </thead>
            <tbody>
              {heatmapRows.map((row: any) => (
                <tr key={row.broker}>
                  <td className="sticky left-0 cursor-pointer bg-slate-900 px-2 py-1 font-mono text-sky-300" onClick={() => setSelectedBroker(row.broker)}>
                    {row.broker}
                  </td>
                  {row.cells.map((cell: any) => {
                    const intensity = Math.min(1, Math.abs(cell.net_value || 0) / maxAbs);
                    const bg = !cell.has_data
                      ? "rgba(71,85,105,0.28)"
                      : (cell.net_value || 0) >= 0
                        ? `rgba(34,197,94,${0.18 + intensity * 0.75})`
                        : `rgba(239,68,68,${0.18 + intensity * 0.75})`;
                    return (
                      <td
                        key={`${row.broker}-${cell.date}`}
                        title={`${row.broker} ${cell.date}: ${cell.net_value ?? "no data"}`}
                        style={{ backgroundColor: bg }}
                        className={`h-8 min-w-8 rounded text-center ${selectedBroker === row.broker ? "ring-1 ring-sky-400" : ""}`}
                      >
                        {cell.has_data ? (cell.net_value >= 0 ? "+" : "-") : ""}
                      </td>
                    );
                  })}
                  <td className="px-2 py-1 text-right font-mono text-slate-300">{(row.total_net || 0).toFixed(0)}</td>
                  <td className="px-2 py-1 text-right text-slate-400">{row.positive_days}/{((periodDetail.trading_days || 0))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
