from __future__ import annotations

from app.models.portfolio import PortfolioSnapshot
from app.services.hyperliquid import sync_hyperliquid_portfolios
import sys
from app.services.schwab import SchwabSession, sync_schwab_portfolio


def main() -> None:

    if len(sys.argv) > 1 and sys.argv[1] == "schwab-auth":
        session = SchwabSession()
        authorization_url, _state = session.build_authorization_url()
        print("Open this URL, log in, approve access, then copy the code from the redirect URL:")
        print(authorization_url)
        code = input("Schwab authorization code: ").strip()
        session.exchange_authorization_code(code)
        print("Schwab authorization saved.")
        return

    snapshots = [sync_schwab_portfolio(), *sync_hyperliquid_portfolios()]

    print("DUCKET BUCKET")
    print("=============")
    print(f"Cash: ${_cash_value(snapshots):,.2f}")
    print(f"Holdings: ${_holdings_value(snapshots):,.2f}")
    print(f"Total: ${_total_value(snapshots):,.2f}")

    for snapshot in snapshots:
        print()
        print(snapshot.account_label.upper())
        print("-" * len(snapshot.account_label))
        print(f"Status: {snapshot.status}")
        print(f"Cash: ${snapshot.cash_value:,.2f}")
        print(f"Holdings: ${snapshot.holdings_value:,.2f}")
        print(f"Total: ${snapshot.total_value:,.2f}")

        print()
        print("Cash")
        for cash in snapshot.cash:
            print(f"- {cash.bucket} {cash.symbol}: {cash.amount:g} = ${cash.value:,.2f}")

        print()
        print("Holdings")
        for holding in snapshot.holdings:
            print(
                f"- {holding.bucket} {holding.symbol}: "
                f"{holding.quantity:g} @ ${holding.price:,.4f} = ${holding.value:,.2f}"
            )


def _cash_value(snapshots: list[PortfolioSnapshot]) -> float:
    return round(sum(snapshot.cash_value for snapshot in snapshots), 2)


def _holdings_value(snapshots: list[PortfolioSnapshot]) -> float:
    return round(sum(snapshot.holdings_value for snapshot in snapshots), 2)


def _total_value(snapshots: list[PortfolioSnapshot]) -> float:
    return round(sum(snapshot.total_value for snapshot in snapshots), 2)


if __name__ == "__main__":
    main()