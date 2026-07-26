"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { DataTable } from "@/components/DataTable";
import { PaginationBar } from "@/components/PaginationBar";

const LIMIT = 50;

export default function RecommendationsPage() {
  const [data, setData] = useState<any>({ items: [], total: 0 });
  const [ticker, setTicker] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [action, setAction] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = { limit: LIMIT, offset };
      if (ticker) params.ticker = ticker;
      if (dateFrom) params.from = dateFrom;
      if (dateTo) params.to = dateTo;
      if (action) params.action = action;
      const r = await api.get("/data/recommendations", { params });
      setData(r.data);
    } catch {}
    setLoading(false);
  }, [action, dateFrom, dateTo, offset, ticker]);

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
        <h1 className="text-xl font-bold">Recommendations</h1>
      </div>

      <div className="card flex flex-wrap gap-3 text-sm">
        <input className="input w-40" placeholder="Ticker" value={ticker} onChange={(e) => setTicker(e.target.value)} />
        <input type="date" className="input w-36" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        <input type="date" className="input w-36" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        <select className="input w-28" value={action} onChange={(e) => setAction(e.target.value)}>
          <option value="">All</option>
          <option value="BUY">Buy</option>
          <option value="SELL">Sell</option>
          <option value="HOLD">Hold</option>
          <option value="WAIT">Wait</option>
          <option value="EXIT">Exit</option>
        </select>
        <button className="btn" onClick={applyFilters} disabled={loading}>
          {loading ? "..." : "Apply"}
        </button>
      </div>

      <div className="card">
        <DataTable
          columns={[
            { key: "ticker", label: "Ticker" },
            { key: "date", label: "Date" },
            { key: "action", label: "Action" },
            { key: "entry", label: "Entry", format: (v: any) => v?.toFixed(0) },
            { key: "stop", label: "Stop", format: (v: any) => v?.toFixed(0) },
            { key: "target", label: "Target", format: (v: any) => v?.toFixed(0) },
            { key: "rationale", label: "Rationale", className: "max-w-xs truncate" },
          ]}
          rows={data.items}
        />
        <PaginationBar offset={offset} limit={LIMIT} total={data.total} onChange={setOffset} />
      </div>
    </div>
  );
}
