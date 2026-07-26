"use client";

import Link from "next/link";

export function TickerLink({ ticker, className = "" }: { ticker: string; className?: string }) {
  const t = ticker?.toUpperCase();
  if (!t) return null;
  return (
    <Link
      href={`/charts/${t}`}
      className={`font-mono text-indigo-400 hover:underline ${className}`}
    >
      {t}
    </Link>
  );
}
