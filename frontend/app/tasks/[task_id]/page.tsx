"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { TickerLink } from "@/components/TickerLink";

export default function TaskDetailPage() {
  const { task_id } = useParams<{ task_id: string }>();
  const [run, setRun] = useState<any>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const r = await api.get(`/tasks/${task_id}`);
      setRun(r.data);
      setError("");
    } catch (e: any) {
      setError(e.response?.data?.detail || "Failed to load task");
    }
  }, [task_id]);

  useEffect(() => {
    load();
    const interval = setInterval(() => {
      load();
    }, 3000);
    return () => clearInterval(interval);
  }, [load]);

  if (error && !run) {
    return (
      <div className="space-y-4">
        <Link href="/" className="text-sm text-indigo-400 hover:underline">&larr; Back to Dashboard</Link>
        <div className="card text-red-400">{error}</div>
      </div>
    );
  }

  if (!run) {
    return (
      <div className="space-y-4">
        <Link href="/" className="text-sm text-indigo-400 hover:underline">&larr; Back to Dashboard</Link>
        <p className="text-slate-400">Loading...</p>
      </div>
    );
  }

  const isRunning = run.status === "PROGRESS" || run.status === "QUEUED" || run.status === "STARTED";
  const statusColor =
    run.status === "FAILURE" || run.status === "ORPHANED" ? "text-red-400"
    : run.status === "SUCCESS" ? "text-emerald-400"
    : run.status === "CANCELLED" ? "text-slate-500"
    : "text-amber-300";

  const errors = run.result?.errors || {};

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <Link href="/" className="text-sm text-indigo-400 hover:underline">&larr; Back to Dashboard</Link>
        {isRunning && <span className="text-xs text-slate-500 animate-pulse">Auto-refresh 3s</span>}
      </div>

      <div className="card space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold">{run.task_name}</h1>
          <span className={`badge text-sm ${statusColor}`}>{run.status}</span>
        </div>

        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <span className="text-slate-400">Task ID</span>
            <div className="font-mono text-xs mt-1 break-all">{run.task_id}</div>
          </div>
          <div>
            <span className="text-slate-400">Stage</span>
            <div className="font-mono mt-1">{run.stage || "-"}</div>
          </div>
          <div>
            <span className="text-slate-400">Progress</span>
            <div className="mt-1">{run.progress}% ({run.processed_tickers}/{run.total_tickers})</div>
          </div>
          <div>
            <span className="text-slate-400">Succeeded / Failed</span>
            <div className="mt-1">
              <span className="text-emerald-400">{run.succeeded_tickers}</span>
              {" / "}
              <span className="text-red-400">{run.failed_tickers}</span>
            </div>
          </div>
          <div>
            <span className="text-slate-400">Started</span>
            <div className="mt-1 text-xs">{run.started_at ? new Date(run.started_at).toLocaleString() : "-"}</div>
          </div>
          <div>
            <span className="text-slate-400">Finished</span>
            <div className="mt-1 text-xs">{run.finished_at ? new Date(run.finished_at).toLocaleString() : "-"}</div>
          </div>
        </div>

        {run.error && (
          <div className="rounded-lg border border-red-800 bg-red-950/40 p-3 text-sm text-red-300">
            <div className="font-semibold mb-1">Error</div>
            <div className="font-mono text-xs whitespace-pre-wrap">{run.error}</div>
          </div>
        )}

        {run.result && (
          <div className="border-t border-slate-800 pt-3">
            <div className="text-sm text-slate-400 mb-2">
              Processed: {run.result.processed} | Succeeded: {run.result.succeeded} | Failed: {run.result.failed}
            </div>
          </div>
        )}
      </div>

      {Object.keys(errors).length > 0 && (
        <div className="card">
          <h2 className="font-semibold mb-3 text-red-400">Failed Tickers ({Object.keys(errors).length})</h2>
          <div className="space-y-2">
            {Object.entries(errors).map(([ticker, errMsg]) => (
                <div key={ticker} className="rounded-lg border border-slate-800 bg-slate-950 p-3 text-sm">
                <div className="font-semibold text-red-300"><TickerLink ticker={ticker} /></div>
                <div className="text-xs text-slate-400 mt-1 font-mono whitespace-pre-wrap">{String(errMsg)}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
