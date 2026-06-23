from __future__ import annotations

from dataclasses import dataclass

from app.models.portfolio import PortfolioSnapshot


@dataclass(frozen=True)
class DucketBucketSnapshot:
    snapshots: list[PortfolioSnapshot]

    @property
    def cash_value(self) -> float:
        return round(sum(snapshot.cash_value for snapshot in self.snapshots), 2)

    @property
    def holdings_value(self) -> float:
        return round(sum(snapshot.holdings_value for snapshot in self.snapshots), 2)

    @property
    def total_value(self) -> float:
        return round(sum(snapshot.total_value for snapshot in self.snapshots), 2)