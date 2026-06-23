from __future__ import annotations

from app.services.hyperliquid import sync_hyperliquid_portfolio


def main() -> None:
    snapshot = sync_hyperliquid_portfolio()

    print("DUCKET BUCKET")
    print("=============")
    print(f"Status: {snapshot.status}")
    print(f"Cash: ${snapshot.cash_value:,.2f}")
    print(f"Holdings: ${snapshot.holdings_value:,.2f}")
    print(f"Total: ${snapshot.total_value:,.2f}")
    print()

    print("Cash")
    for cash in snapshot.cash:
        print(f"- {cash.symbol}: {cash.amount:g} = ${cash.value:,.2f}")

    print()
    print("Holdings")
    for holding in snapshot.holdings:
        print(
            f"- {holding.symbol}: "
            f"{holding.quantity:g} @ ${holding.price:,.4f} = ${holding.value:,.2f}"
        )


if __name__ == "__main__":
    main()