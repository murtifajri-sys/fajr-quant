"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export function PipelineActions() {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function runDailyPipeline() {
    setBusy(true);
    setMessage("Mengantrekan daily pipeline...");
    try {
      const response = await api.post("/tasks/daily-pipeline");
      setMessage(`Queued: ${response.data.task_id}`);
      setTimeout(() => window.location.reload(), 1000);
    } catch (error: any) {
      setMessage(error.response?.data?.detail || error.message);
    } finally {
      setBusy(false);
    }
  }

  async function runBrokerFlowBackfill() {
    setBusy(true);
    setMessage("Mengantrekan broker flow backfill...");
    try {
      const response = await api.post("/tasks/broker-flow-backfill", null, {
        params: { limit: 50, period_days: 30, universe: "idx" },
      });
      setMessage(`Queued: ${response.data.task_id}`);
      setTimeout(() => window.location.reload(), 1000);
    } catch (error: any) {
      setMessage(error.response?.data?.detail || error.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center gap-3">
      <button className="btn" onClick={runDailyPipeline} disabled={busy}>
        {busy ? "Starting..." : "Run Daily Pipeline"}
      </button>
      <button className="btn-secondary" onClick={runBrokerFlowBackfill} disabled={busy}>
        Backfill Broker Flow
      </button>
      <a
        href="http://localhost:5555"
        target="_blank"
        rel="noreferrer"
        className="btn-secondary"
      >
        Open Flower
      </a>
      {message && <span className="text-xs text-slate-400">{message}</span>}
    </div>
  );
}
