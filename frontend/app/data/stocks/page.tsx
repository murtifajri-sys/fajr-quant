"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { DataTable } from "@/components/DataTable";
import { PaginationBar } from "@/components/PaginationBar";

const LIMIT = 100;

export default function StocksPage() {
  const [data, setData] = useState<any>({ items: [], total: 0 });
  const [ticker, setTicker] = useState("");
  const [sector, setSector] = useState("");
  const [board, setBoard] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = { limit: LIMIT, offset };
      if (ticker) params.ticker = ticker;
      if (sector) params.sector = sector;
      if (board) params.board = board;
      const r = await api.get("/data/stocks", { params });
      setData(r.data);
    } catch {}
    setLoading(false);
  }, [board, offset, sector, ticker]);

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
        <h1 className="text-xl font-bold">Stocks</h1>
      </div>

      <div className="card flex flex-wrap gap-3 text-sm">
        <input className="input w-40" placeholder="Search ticker..." value={ticker} onChange={(e) => setTicker(e.target.value)} />
        <input className="input w-40" placeholder="Sector" value={sector} onChange={(e) => setSector(e.target.value)} />
        <select className="input w-40" value={board} onChange={(e) => setBoard(e.target.value)}>
          <option value="">All boards</option>
          <option value="Main">Main</option>
          <option value="Development">Development</option>
          <option value="Acceleration">Acceleration</option>
        </select>
        <button className="btn" onClick={applyFilters} disabled={loading}>
          {loading ? "..." : "Apply"}
        </button>
      </div>

      <div className="card">
        <DataTable
          columns={[
            { key: "ticker", label: "Ticker" },
            { key: "name", label: "Name" },
            { key: "sector", label: "Sector" },
            { key: "industry", label: "Industry", className: "max-w-40 truncate" },
            { key: "board", label: "Board" },
            { key: "listing_date", label: "Listed" },
          ]}
          rows={data.items}
        />
        <PaginationBar offset={offset} limit={LIMIT} total={data.total} onChange={setOffset} />
      </div>
    </div>
  );
}
