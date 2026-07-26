"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export function TokenWarning() {
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    async function check() {
      try {
        const r = await api.get("/tokens");
        const tokens = r.data;
        const active = tokens.find((t: any) => t.active);
        if (!active) return setProblem("Tidak ada token Stockbit aktif.");
        if (active.is_expired) return setProblem("Stockbit token expired.");
        if (active.status === "error") return setProblem(active.last_error || "Token error.");
        if (active.warning) return setProblem(active.warning);
        setProblem(null);
      } catch {
        setProblem("Gagal cek status token.");
      }
    }
    check();
    const interval = setInterval(check, 30000);
    return () => clearInterval(interval);
  }, []);

  if (!problem) return null;

  return (
    <div className={`rounded-xl border p-4 text-sm ${problem.includes("akan expired") ? "border-amber-700 bg-amber-950/60 text-amber-200" : "border-red-700 bg-red-950/60 text-red-200"}`}>
      <div className="font-semibold">Stockbit token perlu diperbarui</div>
      <div className="mt-1">
        {problem}{" "}
        <a href="/settings/tokens" className="underline">Buka pengaturan token</a>
      </div>
    </div>
  );
}
