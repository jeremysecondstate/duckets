from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


Source = Literal["schwab", "hyperliquid"]


@dataclass(frozen=True)
class Holding:
    symbol: str
    quantity: float
    price: float
    value: float
    source: Source
    asset_type: str = "unknown"


@dataclass(frozen=True)
class CashBalance:
    symbol: str
    amount: float
    value: float
    source: Source


@dataclass(frozen=True)
class PortfolioSnapshot:
    source: Source
    account_label: str
    cash: list[CashBalance] = field(default_factory=list)
    holdings: list[Holding] = field(default_factory=list)
    synced_at: datetime | None = None
    status: str = "not synced"

    @property
    def cash_value(self) -> float:
        return round(sum(cash.value for cash in self.cash), 2)

    @property
    def holdings_value(self) -> float:
        return round(sum(holding.value for holding in self.holdings), 2)

    @property
    def total_value(self) -> float:
        return round(self.cash_value + self.holdings_value, 2)