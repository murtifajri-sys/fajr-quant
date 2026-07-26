"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { DataTable } from "@/components/DataTable";
import { PaginationBar } from "@/components/PaginationBar";

const LIMIT = 50;

function fmtTechPayload(method: string, p: any) {
  if (!p) return "-";
  if (method === "trend_structure") return `ema20:${p.ema20?.toFixed(0)||"-"} ema50:${p.ema50?.toFixed(0)||"-"} slope:${(p.slope50||0).toFixed(4)} ${p.structure}`;
  if (method === "price_action") return `ATR:${p.atr?.toFixed(0)||"-"} SR:${p.nearest_resistance||"-"}/${p.nearest_support||"-"}`;
  if (method === "volume_breakout") return `spike:${(p.spike_ratio||0).toFixed(2)}x obv:${p.obv_rising?"up":"dn"} adl:${p.adl_rising?"up":"dn"}`;
  if (method === "candlestick") return `pattern:${p.pattern} body:${p.body?.toFixed(0)}`;
  if (method === "relative_strength") return `RS:${(p.rs||0).toFixed(3)} mom:${(p.rs_mom_20d||0).toFixed(3)}`;
  if (method === "harmonic") return `pattern:${p.pattern||"none"}`;
  if (method === "elliott_wave") return `label:${p.label}`;
  if (method === "breakout") return `passed:${p.passed}/7 ema20:${p.ema20?.toFixed(0)} rsi:${p.rsi14?.toFixed(0)} vol:${p.vol_ratio?.toFixed(2)}x`;
  return JSON.stringify(p).slice(0, 80);
}

export default function TechnicalPage() {
  const [data, setData] = useState<any>({ items: [], total: 0 });
  const [ticker, setTicker] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [method, setMethod] = useState("");
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
      if (method) params.method = method;
      if (minScore) params.min_score = minScore;
      const r = await api.get("/data/technical", { params });
      setData(r.data);
    } catch {}
    setLoading(false);
  }, [dateFrom, dateTo, method, minScore, offset, ticker]);

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
        <h1 className="text-xl font-bold">Technical Indicators</h1>
      </div>

      <div className="card flex flex-wrap gap-3 text-sm">
        <input className="input w-40" placeholder="Ticker" value={ticker} onChange={(e) => setTicker(e.target.value)} />
        <input type="date" className="input w-36" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        <input type="date" className="input w-36" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        <select className="input w-48" value={method} onChange={(e) => setMethod(e.target.value)}>
          <option value="">All methods</option>
          <option value="trend_structure">Trend Structure</option>
          <option value="price_action">Price Action</option>
          <option value="volume_breakout">Volume Breakout</option>
          <option value="harmonic">Harmonic</option>
          <option value="relative_strength">Relative Strength</option>
          <option value="candlestick">Candlestick</option>
          <option value="elliott_wave">Elliott Wave</option>
          <option value="indicator">Indicator</option>
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
            { key: "method", label: "Method" },
            { key: "name", label: "Name" },
            { key: "score", label: "Score", format: (v: any) => v?.toFixed(0) },
            { key: "payload", label: "Details", format: (_v: any, row: any) => fmtTechPayload(row.method, row.payload), className: "max-w-sm truncate text-slate-400" },
          ]}
          rows={data.items}
        />
        <PaginationBar offset={offset} limit={LIMIT} total={data.total} onChange={setOffset} />
      </div>
    </div>
  );
}
