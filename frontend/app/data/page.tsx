import Link from "next/link";

const sections = [
  { href: "/data/prices", label: "Prices", desc: "OHLCV daily price data, filter by ticker, date, source" },
  { href: "/data/bandarmology", label: "Bandarmology", desc: "Broker flow patterns, filter by label, detected, broker" },
  { href: "/data/foreign", label: "Foreign Flow", desc: "Net foreign buy/sell per ticker" },
  { href: "/data/technical", label: "Technical", desc: "Indicator signals, filter by method" },
  { href: "/data/scores", label: "Scores", desc: "Composite score history, filter by phase" },
  { href: "/data/recommendations", label: "Recommendations", desc: "AI recommendations, filter by action" },
  { href: "/data/stocks", label: "Stocks", desc: "Stock universe, filter by sector, industry, board" },
];

export default function DataIndexPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Data Explorer</h1>
      <div className="grid grid-cols-2 gap-3">
        {sections.map((s) => (
          <Link key={s.href} href={s.href} className="card hover:border-slate-600 transition-colors">
            <div className="font-semibold">{s.label}</div>
            <div className="text-sm text-slate-400 mt-1">{s.desc}</div>
          </Link>
        ))}
      </div>
    </div>
  );
}
