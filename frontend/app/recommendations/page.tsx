"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { TickerLink } from "@/components/TickerLink";

export default function RecommendationsPage() {
  const [recs, setRecs] = useState<any[]>([]);
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get("/recommendations", { params: { limit: 50, date } });
      setRecs(r.data);
    } catch {}
    setLoading(false);
  }, [date]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Recommendations</h1>
        <input
          type="date"
          className="input w-40"
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />
      </div>
      <div className="card">
        {loading ? (
          <p className="text-slate-400 text-sm">Loading...</p>
        ) : recs.length === 0 ? (
          <p className="text-slate-400 text-sm">No recommendations for {date}.</p>
        ) : (
          <div className="space-y-3">
            {recs.map((r, i) => (
              <div key={i} className="border-b border-slate-800 pb-3">
                <div className="flex items-center gap-3">
                  <TickerLink ticker={r.ticker} className="font-bold" />
                  <span className="badge bg-indigo-600">{r.action}</span>
                  <span className="text-xs text-slate-400">{r.date}</span>
                </div>
                <div className="text-sm mt-1 text-slate-300">
                  Entry {r.entry ?? "-"} · Stop {r.stop ?? "-"} · Target {r.target ?? "-"}
                </div>
                {r.rationale && <p className="text-sm text-slate-400 mt-1">{r.rationale}</p>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
