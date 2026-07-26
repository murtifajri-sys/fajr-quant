"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { DataTable } from "@/components/DataTable";
import { PaginationBar } from "@/components/PaginationBar";

const LIMIT = 50;

export default function ScoresPage() {
  const [data, setData] = useState<any>({ items: [], total: 0 });
  const [ticker, setTicker] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [phase, setPhase] = useState("");
  const [minComp, setMinComp] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = { limit: LIMIT, offset };
      if (ticker) params.ticker = ticker;
      if (dateFrom) params.from = dateFrom;
      if (dateTo) params.to = dateTo;
      if (phase) params.phase = phase;
      if (minComp) params.min_composite = minComp;
      const r = await api.get("/data/scores", { params });
      setData(r.data);
    } catch {}
    setLoading(false);
  }, [dateFrom, dateTo, minComp, offset, phase, ticker]);

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
        <h1 className="text-xl font-bold">Scores</h1>
      </div>

      <div className="card flex flex-wrap gap-3 text-sm">
        <input className="input w-40" placeholder="Ticker" value={ticker} onChange={(e) => setTicker(e.target.value)} />
        <input type="date" className="input w-36" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        <input type="date" className="input w-36" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        <select className="input w-40" value={phase} onChange={(e) => setPhase(e.target.value)}>
          <option value="">All phases</option>
          <option value="accumulation">Accumulation</option>
          <option value="mark_up">Mark Up</option>
          <option value="distribution">Distribution</option>
          <option value="mark_down">Mark Down</option>
        </select>
        <input className="input w-28" type="number" placeholder="Min Composite" value={minComp} onChange={(e) => setMinComp(e.target.value)} />
        <button className="btn" onClick={applyFilters} disabled={loading}>
          {loading ? "..." : "Apply"}
        </button>
      </div>

      <div className="card">
        <DataTable
          columns={[
            { key: "ticker", label: "Ticker" },
            { key: "date", label: "Date" },
            { key: "composite", label: "Composite", format: (v: any) => v?.toFixed(1) },
            { key: "phase", label: "Phase" },
            { key: "confidence", label: "Confidence", format: (v: any) => v?.toFixed(1) },
          ]}
          rows={data.items}
        />
        <PaginationBar offset={offset} limit={LIMIT} total={data.total} onChange={setOffset} />
      </div>
    </div>
  );
}
