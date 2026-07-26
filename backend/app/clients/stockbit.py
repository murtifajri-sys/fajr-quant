"""Stockbit (Exodus) API client.

Wraps the endpoints documented in data_sources.md:
- GET /chartbit/{symbol}/price/daily                 (daily prices + foreign flow)
- GET /marketdetectors/{symbol}                        (broker/investor flow)
- GET /emitten/{symbol}/profile                        (company info)
- GET /insider/shareholding/composition/companies/{symbol}
- GET /insider/company/majorholder                     (major shareholders)
"""
import time
from datetime import date

from sqlalchemy.orm import Session

from app.clients.base import BaseClient, get_active_token, mark_token_used
from app.core.config import settings
from app.core.logging import log


class StockbitClient(BaseClient):
    def get_daily_prices(
        self, symbol: str, start: date, end: date, limit: int = 1000, page: int = 1
    ) -> dict:
        assert self.db, "StockbitClient needs a db session"
        token_row, token = get_active_token(self.db)
        params = {
            # Stockbit's chartbit endpoint uses reversed date semantics:
            # `from` is the newer bound and `to` is the older bound.
            "from": end.isoformat(),
            "to": start.isoformat(),
            "limit": limit,
        }
        try:
            data = self._request(
                "GET", f"/chartbit/{symbol.upper()}/price/daily", token, params
            )
            mark_token_used(self.db, token_row, ok=True)
            time.sleep(settings.STOCKBIT_RATE_LIMIT_DELAY)
            return data
        except Exception as e:
            mark_token_used(self.db, token_row, ok=False, err=str(e))
            raise

    def get_market_detectors(
        self,
        symbol: str,
        start: date,
        end: date,
        transaction_type: str = "TRANSACTION_TYPE_NET",
        market_board: str = "MARKET_BOARD_REGULER",
        investor_type: str = "INVESTOR_TYPE_ALL",
        limit: int = 100,
    ) -> dict:
        assert self.db
        token_row, token = get_active_token(self.db)
        params = {
            "from": start.isoformat(),
            "to": end.isoformat(),
            "transaction_type": transaction_type,
            "market_board": market_board,
            "investor_type": investor_type,
            "limit": limit,
        }
        try:
            data = self._request(
                "GET", f"/marketdetectors/{symbol.upper()}", token, params
            )
            mark_token_used(self.db, token_row, ok=True)
            time.sleep(settings.STOCKBIT_RATE_LIMIT_DELAY)
            return data
        except Exception as e:
            mark_token_used(self.db, token_row, ok=False, err=str(e))
            raise

    def get_company_profile(self, symbol: str) -> dict:
        assert self.db
        token_row, token = get_active_token(self.db)
        try:
            data = self._request("GET", f"/emitten/{symbol.upper()}/profile", token)
            mark_token_used(self.db, token_row, ok=True)
            time.sleep(settings.STOCKBIT_RATE_LIMIT_DELAY)
            return data
        except Exception as e:
            mark_token_used(self.db, token_row, ok=False, err=str(e))
            raise

    def get_shareholder_composition(self, symbol: str, start: date, end: date) -> dict:
        assert self.db
        token_row, token = get_active_token(self.db)
        params = {"period_start": start.isoformat(), "period_end": end.isoformat()}
        try:
            data = self._request(
                "GET",
                f"/insider/shareholding/composition/companies/{symbol.upper()}",
                token,
                params,
            )
            mark_token_used(self.db, token_row, ok=True)
            time.sleep(settings.STOCKBIT_RATE_LIMIT_DELAY)
            return data
        except Exception as e:
            mark_token_used(self.db, token_row, ok=False, err=str(e))
            raise

    def get_major_holders(self, symbol: str, page: int = 1) -> dict:
        assert self.db
        token_row, token = get_active_token(self.db)
        params = {"insider": "", "symbol": symbol.upper(), "date_start": "", "date_end": "", "page": page}
        try:
            data = self._request(
                "GET", "/insider/company/majorholder", token, params
            )
            mark_token_used(self.db, token_row, ok=True)
            time.sleep(settings.STOCKBIT_RATE_LIMIT_DELAY)
            return data
        except Exception as e:
            mark_token_used(self.db, token_row, ok=False, err=str(e))
            raise
