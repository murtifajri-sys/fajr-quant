import Link from "next/link";

const items = [
  { href: "/watchlist", label: "Watchlist", desc: "Manage tickers used by watchlist-based screens" },
  { href: "/settings/tokens", label: "Tokens", desc: "Manage Stockbit API tokens" },
  { href: "/settings/telegram", label: "Telegram", desc: "Configure Telegram notifications" },
];

export default function SettingsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Settings</h1>
      <div className="grid gap-3">
        {items.map((item) => (
          <Link key={item.href} href={item.href} className="card hover:border-slate-600 transition-colors">
            <div className="font-semibold">{item.label}</div>
            <div className="text-sm text-slate-400 mt-1">{item.desc}</div>
          </Link>
        ))}
      </div>
    </div>
  );
}
