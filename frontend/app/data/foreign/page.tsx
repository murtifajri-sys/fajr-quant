"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { DataTable } from "@/components/DataTable";
import { PaginationBar } from "@/components/PaginationBar";

const LIMIT = 50;

export default function ForeignFlowPage() {
  const [data, setData] = useState<any>({ items: [], total: 0 });
  const [ticker, setTicker] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [minNet, setMinNet] = useState("");
  const [maxNet, setMaxNet] = useState("");
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
      if (minNet) params.min_net = minNet;
      if (maxNet) params.max_net = maxNet;
      if (minScore) params.min_score = minScore;
      const r = await api.get("/data/foreign-flow", { params });
      setData(r.data);
    } catch {}
    setLoading(false);
  }, [dateFrom, dateTo, maxNet, minNet, minScore, offset, ticker]);

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

  const fmtB = (v: any) => {
    if (v == null) return "-";
    const b = v / 1e9;
    return `${b >= 0 ? "+" : ""}${b.toFixed(2)}B`;
  };

  const fmtPct4 = (v: any) => v != null ? `${v.toFixed(4)}%` : "-";

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Link href="/data" className="text-sm text-indigo-400 hover:underline">&larr; Data</Link>
        <h1 className="text-xl font-bold">Foreign Flow</h1>
      </div>

      <div className="card flex flex-wrap gap-3 text-sm">
        <input className="input w-40" placeholder="Ticker" value={ticker} onChange={(e) => setTicker(e.target.value)} />
        <input type="date" className="input w-36" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        <input type="date" className="input w-36" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        <input className="input w-28" type="number" placeholder="Min Net" value={minNet} onChange={(e) => setMinNet(e.target.value)} />
        <input className="input w-28" type="number" placeholder="Max Net" value={maxNet} onChange={(e) => setMaxNet(e.target.value)} />
        <input className="input w-28" type="number" placeholder="Min Score" value={minScore} onChange={(e) => setMinScore(e.target.value)} />
        <button className="btn" onClick={applyFilters} disabled={loading}>
          {loading ? "..." : "Apply"}
        </button>
      </div>

      <div className="card">
        <DataTable
          columns={[
            { key: "ticker", label: "Ticker" },
            { key: "date", label: "Date" },
            { key: "foreign_buy", label: "Buy", format: (v: any) => v ? (v / 1e9).toFixed(2) + "B" : "-", className: "text-right" },
            { key: "foreign_sell", label: "Sell", format: (v: any) => v ? (v / 1e9).toFixed(2) + "B" : "-", className: "text-right" },
            { key: "net_foreign", label: "Net", format: fmtB, className: "text-right" },
            { key: "net_foreign_pct", label: "Net %", format: (v: any) => v != null ? v.toFixed(2) + "%" : "-", className: "text-right" },
            { key: "pct_market_cap", label: "% MCap", format: fmtPct4, className: "text-right" },
            { key: "pct_avg_daily_value", label: "% ADV", format: fmtPct4, className: "text-right" },
            { key: "score", label: "Score", format: (v: any) => v?.toFixed(0), className: "text-right" },
          ]}
          rows={data.items}
        />
        <PaginationBar offset={offset} limit={LIMIT} total={data.total} onChange={setOffset} />
      </div>
    </div>
  );
}
