"use client";
import { useState } from "react";
import Link from "next/link";

export default function ChartsIndex() {
  const [t, setT] = useState("");
  return (
    <div className="space-y-6 max-w-md">
      <h1 className="text-2xl font-bold">Charts</h1>
      <div className="card space-y-3">
        <label className="text-sm text-slate-400">Enter ticker</label>
        <div className="flex gap-2">
          <input className="input" value={t} onChange={(e) => setT(e.target.value.toUpperCase())} placeholder="BBCA" />
          <Link href={`/charts/${t || "BBCA"}`} className="btn">Open</Link>
        </div>
      </div>
    </div>
  );
}
