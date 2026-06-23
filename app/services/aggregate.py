from __future__ import annotations

from dataclasses import dataclass

from app.models.portfolio import PortfolioSnapshot


@dataclass(frozen=True)
class DucketBucketSnapshot:
    schwab: PortfolioSnapshot
    hyperliquid: PortfolioSnapshot

    @property
    def cash_value(self) -> float:
        return round(self.schwab.cash_value + self.hyperliquid.cash_value, 2)

    @property
    def holdings_value(self) -> float:
        return round(self.schwab.holdings_value + self.hyperliquid.holdings_value, 2)

    @property
    def total_value(self) -> float:
        return round(self.cash_value + self.holdings_value, 2)