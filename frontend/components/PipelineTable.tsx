"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

function CancelButton({ taskId, status, onCancel }: { taskId: string; status: string; onCancel: () => void }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  if (status !== "QUEUED" && status !== "PROGRESS" && status !== "STARTED") return null;

  async function cancel() {
    if (!confirm(`Batalkan task ${taskId.slice(0, 8)}...?`)) return;
    setBusy(true);
    try {
      await api.post(`/tasks/${taskId}/cancel`);
      setMsg("Cancelled");
      onCancel();
    } catch (e: any) {
      setMsg(e.response?.data?.detail || "Failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <button className="btn-danger text-xs px-2 py-0.5" onClick={cancel} disabled={busy}>
      {busy ? "..." : msg || "Cancel"}
    </button>
  );
}

export function PipelineTable({ runs: initialRuns }: { runs: any[] }) {
  const [runs, setRuns] = useState(initialRuns);

  async function load() {
    try {
      const r = await api.get("/tasks/runs", { params: { limit: 10 } });
      setRuns(r.data);
    } catch {}
  }

  useEffect(() => {
    const hasRunning = runs.some(
      (r: any) => r.status === "PROGRESS" || r.status === "QUEUED" || r.status === "STARTED"
    );
    const interval = setInterval(load, 3000);
    return () => clearInterval(interval);
  }, [runs]);

  return (
    <div className="card">
      <h2 className="font-semibold mb-3">Pipeline Status</h2>
      {runs.length === 0 ? (
        <p className="text-slate-400 text-sm">Belum ada pipeline yang dijalankan.</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-slate-400">
              <th className="text-left">Task</th>
              <th>Status</th>
              <th>Stage</th>
              <th>Progress</th>
              <th>Success</th>
              <th>Failed</th>
              <th>Started</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run: any) => (
              <tr key={run.task_id} className="border-t border-slate-800">
                <td className="py-1">
                  <Link href={`/tasks/${run.task_id}`} className="text-indigo-400 hover:underline font-mono text-xs">
                    {run.task_name}
                  </Link>
                </td>
                <td className={`text-center ${run.status === "FAILURE" || run.status === "ORPHANED" ? "text-red-400" : run.status === "SUCCESS" ? "text-emerald-400" : run.status === "CANCELLED" ? "text-slate-500" : "text-amber-300"}`}>{run.status}</td>
                <td className="text-center font-mono text-xs">{run.stage || "-"}</td>
                <td className="text-center">{run.progress}% ({run.processed_tickers}/{run.total_tickers})</td>
                <td className="text-center">{run.succeeded_tickers}</td>
                <td className="text-center">{run.failed_tickers}</td>
                <td className="text-center text-xs">{run.started_at?.slice(0, 16) || "-"}</td>
                <td className="text-center"><CancelButton taskId={run.task_id} status={run.status} onCancel={load} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
