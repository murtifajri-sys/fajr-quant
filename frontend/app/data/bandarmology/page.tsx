"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { DataTable } from "@/components/DataTable";
import { PaginationBar } from "@/components/PaginationBar";

const LIMIT = 50;

function fmtMoney(v?: number | null) {
  if (v === null || v === undefined) return "-";
  const abs = Math.abs(v);
  if (abs >= 1e12) return (v / 1e12).toFixed(2) + "T";
  if (abs >= 1e9) return (v / 1e9).toFixed(2) + "B";
  if (abs >= 1e6) return (v / 1e6).toFixed(1) + "M";
  return v.toFixed(0);
}

function fmtPct(v?: number | null) {
  if (v === null || v === undefined) return "-";
  return `${v.toFixed(4)}%`;
}

function formatPayload(label: string, p: any) {
  if (!p) return "-";
  if (label === "hidden_accumulation") return `vol:${(p.volume_spike||0).toFixed(2)} narrow:${p.narrow_range} flat:${p.flat} net:${fmtMoney(p.net_flow)}`;
  if (label === "silent_accumulation") return `broker:${p.top_broker||"-"} ratio:${(p.consistency_ratio||0).toFixed(2)} drift:${((p.price_drift||0)*100).toFixed(1)}%`;
  if (label === "shakeout") return `drop:${((p.drop_pct||0)*100).toFixed(1)}% recv:${((p.recover_pct||0)*100).toFixed(1)}% vol:${(p.volume_spike||0).toFixed(2)}`;
  if (label === "absorption") return `net:${fmtMoney(p.big_broker_net)} buyers:${p.n_buyers||0} top:${p.top_buyer||"-"}`;
  if (label === "bandar_positioning") return `acc:${fmtMoney(p.accumulation)} dist:${fmtMoney(p.distribution)} net:${fmtMoney(p.net)}`;
  if (label === "consistency") return `days:${p.positive_days}/${p.total_days} net:${fmtMoney(p.net_total)}`;
  return JSON.stringify(p).slice(0, 80);
}

export default function BandarmologyPage() {
  const [data, setData] = useState<any>({ items: [], total: 0 });
  const [ticker, setTicker] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [label, setLabel] = useState("");
  const [detected, setDetected] = useState("");
  const [minScore, setMinScore] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = { limit: LIMIT, offset };
      if (ticker) params.ticker = ticker;
      if (dateFrom) params.from = dateFrom;
      if (dateTo) params.to = dateTo;
      if (label) params.label = label;
      if (detected !== "") params.detected = detected;
      if (minScore) params.min_score = minScore;
      const r = await api.get("/data/bandarmology", { params });
      setData(r.data);
    } catch {}
    setLoading(false);
  }, [dateFrom, dateTo, detected, label, minScore, offset, ticker]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  function applyFilters() {
    if (offset === 0) {
      fetchData();
      return;
    }
    setOffset(0);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Link href="/data" className="text-sm text-indigo-400 hover:underline">&larr; Data</Link>
        <h1 className="text-xl font-bold">Bandarmology</h1>
      </div>

      <div className="card flex flex-wrap gap-3 text-sm">
        <input className="input w-40" placeholder="Ticker" value={ticker} onChange={(e) => setTicker(e.target.value)} />
        <input type="date" className="input w-36" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        <input type="date" className="input w-36" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        <select className="input w-48" value={label} onChange={(e) => setLabel(e.target.value)}>
          <option value="">All labels</option>
          <option value="hidden_accumulation">Hidden Accumulation</option>
          <option value="silent_accumulation">Silent Accumulation</option>
          <option value="shakeout">Shakeout</option>
          <option value="absorption">Absorption</option>
          <option value="bandar_positioning">Bandar Positioning</option>
          <option value="consistency">Consistency</option>
        </select>
        <select className="input w-28" value={detected} onChange={(e) => setDetected(e.target.value)}>
          <option value="">Any</option>
          <option value="true">Detected</option>
          <option value="false">Not detected</option>
        </select>
        <input className="input w-24" type="number" placeholder="Min Score" value={minScore} onChange={(e) => setMinScore(e.target.value)} />
        <button className="btn" onClick={applyFilters} disabled={loading}>
          {loading ? "..." : "Apply"}
        </button>
      </div>

      <div className="card">
        <DataTable
          columns={[
            { key: "ticker", label: "Ticker" },
            { key: "date", label: "Date" },
            { key: "label", label: "Label", className: "max-w-36 truncate" },
            { key: "detected", label: "Detected", format: (v: any) => v ? "Yes" : "No" },
            { key: "flow_value", label: "Flow", format: (v: any) => fmtMoney(v), className: "text-right" },
            { key: "pct_market_cap", label: "% MCap", format: (v: any) => fmtPct(v), className: "text-right" },
            { key: "pct_avg_daily_value", label: "% ADV", format: (v: any) => fmtPct(v), className: "text-right" },
            { key: "score", label: "Score", format: (v: any) => v?.toFixed(0), className: "text-right" },
            { key: "payload", label: "Details", format: (_v: any, row: any) => formatPayload(row.label, row.payload), className: "max-w-xs truncate text-slate-400" },
          ]}
          rows={data.items}
        />
        <PaginationBar offset={offset} limit={LIMIT} total={data.total} onChange={setOffset} />
      </div>
    </div>
  );
}
