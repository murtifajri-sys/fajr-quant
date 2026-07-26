import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Fajr Quant", description: "Stock analysis platform" };

const nav = [
  { href: "/", label: "Dashboard" },
  { href: "/screener", label: "Screener" },
  { href: "/ai-screener", label: "AI Screener" },
  { href: "/ipo-screener", label: "IPO Screener" },
  { href: "/watchlist", label: "Watchlist" },
  { href: "/data", label: "Data" },
  { href: "/charts", label: "Charts" },
  { href: "/recommendations", label: "Recommendations" },
  { href: "/settings", label: "Settings" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <header className="border-b border-slate-800 px-6 py-3 flex items-center gap-6">
          <div className="font-bold text-lg">Fajr Quant</div>
          <nav className="flex gap-4 text-sm">
            {nav.map((n) => (
              <Link key={n.href} href={n.href} className="text-slate-300 hover:text-white">
                {n.label}
              </Link>
            ))}
          </nav>
        </header>
        <main className="p-6 max-w-7xl mx-auto">{children}</main>
      </body>
    </html>
  );
}
