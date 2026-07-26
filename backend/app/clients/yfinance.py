"""yfinance client used as price fallback."""
from datetime import date

import yfinance as yf

from app.core.config import settings
from app.core.logging import log


class YFinanceClient:
    def get_daily_prices(self, symbol: str, start: date, end: date) -> list[dict]:
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start.isoformat(), end=end.isoformat(), auto_adjust=False)
        if df is None or df.empty:
            return []
        df = df.reset_index()
        rows = []
        for _, r in df.iterrows():
            d = r.get("Date")
            if hasattr(d, "date"):
                d = d.date()
            rows.append(
                {
                    "date": d,
                    "open": float(r.get("Open")) if r.get("Open") == r.get("Open") else None,
                    "high": float(r.get("High")) if r.get("High") == r.get("High") else None,
                    "low": float(r.get("Low")) if r.get("Low") == r.get("Low") else None,
                    "close": float(r.get("Close")) if r.get("Close") == r.get("Close") else None,
                    "adj_close": float(r.get("Adj Close"))
                    if r.get("Adj Close") == r.get("Adj Close")
                    else None,
                    "volume": float(r.get("Volume")) if r.get("Volume") == r.get("Volume") else None,
                }
            )
        return rows

    def get_benchmark_prices(self, symbol: str = "^JKSE", start: date | None = None, end: date | None = None) -> list[dict]:
        return self.get_daily_prices(symbol, start or date(2000, 1, 1), end or date.today())
