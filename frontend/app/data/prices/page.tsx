"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { DataTable } from "@/components/DataTable";
import { PaginationBar } from "@/components/PaginationBar";

const LIMIT = 50;

export default function PricesPage() {
  const [data, setData] = useState<any>({ items: [], total: 0 });
  const [ticker, setTicker] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [source, setSource] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = { limit: LIMIT, offset };
      if (ticker) params.ticker = ticker;
      if (dateFrom) params.from = dateFrom;
      if (dateTo) params.to = dateTo;
      if (source) params.source = source;
      const r = await api.get("/data/prices", { params });
      setData(r.data);
    } catch {}
    setLoading(false);
  }, [dateFrom, dateTo, offset, source, ticker]);

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
        <h1 className="text-xl font-bold">Prices</h1>
      </div>

      <div className="card flex flex-wrap gap-3 text-sm">
        <input className="input w-40" placeholder="Ticker (e.g. BBRI,BBCA)" value={ticker} onChange={(e) => setTicker(e.target.value)} />
        <input type="date" className="input w-36" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} placeholder="From" />
        <input type="date" className="input w-36" value={dateTo} onChange={(e) => setDateTo(e.target.value)} placeholder="To" />
        <select className="input w-32" value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="">All sources</option>
          <option value="stockbit">Stockbit</option>
          <option value="yfinance">YFinance</option>
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
            { key: "open", label: "Open", format: (v: any) => v?.toFixed(0) },
            { key: "high", label: "High", format: (v: any) => v?.toFixed(0) },
            { key: "low", label: "Low", format: (v: any) => v?.toFixed(0) },
            { key: "close", label: "Close", format: (v: any) => v?.toFixed(0) },
            { key: "volume", label: "Volume", format: (v: any) => v ? (v / 1000).toFixed(0) + "K" : "-" },
            { key: "source", label: "Source" },
          ]}
          rows={data.items}
        />
        <PaginationBar offset={offset} limit={LIMIT} total={data.total} onChange={setOffset} />
      </div>
    </div>
  );
}
