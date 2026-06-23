from __future__ import annotations

from datetime import datetime
from typing import Any

import requests

from app.config import hyperliquid_info_url, hyperliquid_wallet_address
from app.models.portfolio import CashBalance, Holding, PortfolioSnapshot


ZERO_EPSILON = 0.00000001
CASH_SYMBOLS = {"USDC", "USD"}


class HyperliquidInfoClient:
    def __init__(self, info_url: str | None = None, timeout_seconds: int = 30) -> None:
        self.info_url = (info_url or hyperliquid_info_url()).strip()
        self.timeout_seconds = timeout_seconds

    def post_info(self, payload: dict[str, Any]) -> Any:
        response = requests.post(
            self.info_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()


def sync_hyperliquid_portfolio() -> PortfolioSnapshot:
    wallet_address = _normalize_wallet_address(hyperliquid_wallet_address())
    client = HyperliquidInfoClient()

    clearinghouse_state = client.post_info({"type": "clearinghouseState", "user": wallet_address})
    spot_state = client.post_info({"type": "spotClearinghouseState", "user": wallet_address})
    all_mids = client.post_info({"type": "allMids"})

    if not isinstance(clearinghouse_state, dict):
        raise RuntimeError("Hyperliquid clearinghouseState returned an unexpected response.")
    if not isinstance(spot_state, dict):
        raise RuntimeError("Hyperliquid spotClearinghouseState returned an unexpected response.")
    if not isinstance(all_mids, dict):
        raise RuntimeError("Hyperliquid allMids returned an unexpected response.")

    perp_holdings = _perp_holdings(clearinghouse_state)
    spot_cash, spot_holdings = _spot_balances(spot_state, all_mids)

    perp_account_value = _perp_account_value(clearinghouse_state)
    perp_notional = round(sum(holding.value for holding in perp_holdings), 2)
    perp_cash_value = round(perp_account_value - perp_notional, 2)

    cash = list(spot_cash)
    if abs(perp_cash_value) > 0.005:
        cash.append(
            CashBalance(
                symbol="USDC",
                amount=perp_cash_value,
                value=perp_cash_value,
                source="hyperliquid",
            )
        )

    return PortfolioSnapshot(
        source="hyperliquid",
        cash=cash,
        holdings=[*perp_holdings, *spot_holdings],
        synced_at=datetime.now(),
        status=f"synced {wallet_address[:6]}...{wallet_address[-4:]}",
    )


def _perp_holdings(clearinghouse_state: dict[str, Any]) -> list[Holding]:
    holdings: list[Holding] = []

    for row in _dict_rows(clearinghouse_state.get("assetPositions")):
        position = row.get("position") if isinstance(row.get("position"), dict) else row

        coin = str(position.get("coin") or "").strip().upper()
        signed_size = _to_float(position.get("szi") or position.get("size")) or 0.0

        if not coin or abs(signed_size) <= ZERO_EPSILON:
            continue

        quantity = abs(signed_size)
        value = abs(_to_float(position.get("positionValue")) or 0.0)
        price = _first_number(position, ("markPx", "oraclePx", "midPx", "entryPx"))

        if price is None:
            price = value / quantity if quantity > ZERO_EPSILON else 0.0

        side_suffix = "PERP" if signed_size > 0 else "PERP-SHORT"

        holdings.append(
            Holding(
                symbol=f"{coin}-{side_suffix}",
                quantity=round(quantity, 8),
                price=round(price, 8),
                value=round(value, 2),
                source="hyperliquid",
                asset_type="perp",
            )
        )

    return holdings


def _spot_balances(
    spot_state: dict[str, Any],
    all_mids: dict[str, Any],
) -> tuple[list[CashBalance], list[Holding]]:
    cash: list[CashBalance] = []
    holdings: list[Holding] = []

    for balance in _dict_rows(spot_state.get("balances")):
        symbol = str(balance.get("coin") or balance.get("token") or "").strip().upper()
        quantity = _first_number(balance, ("total", "balance", "amount")) or 0.0

        if not symbol or quantity <= ZERO_EPSILON:
            continue

        value = _spot_value(symbol, quantity, balance, all_mids)

        if symbol in CASH_SYMBOLS:
            cash.append(
                CashBalance(
                    symbol=symbol,
                    amount=round(quantity, 8),
                    value=round(value, 2),
                    source="hyperliquid",
                )
            )
            continue

        price = value / quantity

        holdings.append(
            Holding(
                symbol=f"{symbol}-SPOT",
                quantity=round(quantity, 8),
                price=round(price, 8),
                value=round(value, 2),
                source="hyperliquid",
                asset_type="spot",
            )
        )

    return cash, holdings


def _spot_value(
    symbol: str,
    quantity: float,
    balance: dict[str, Any],
    all_mids: dict[str, Any],
) -> float:
    direct_value = _first_number(balance, ("usdValue", "usdcValue", "currentValue", "marketValue", "value"))
    if direct_value is not None:
        return direct_value

    if symbol in CASH_SYMBOLS:
        return quantity

    mid_price = _to_float(all_mids.get(symbol))
    if mid_price is None:
        raise RuntimeError(f"Could not price Hyperliquid spot balance: {symbol}")

    return quantity * mid_price


def _perp_account_value(clearinghouse_state: dict[str, Any]) -> float:
    margin_summary = clearinghouse_state.get("marginSummary")
    cross_margin_summary = clearinghouse_state.get("crossMarginSummary")

    for summary in (margin_summary, cross_margin_summary):
        if not isinstance(summary, dict):
            continue

        account_value = _to_float(summary.get("accountValue"))
        if account_value is not None:
            return account_value

    return 0.0


def _normalize_wallet_address(address: str) -> str:
    normalized = address.strip()

    if not normalized.startswith("0x") or len(normalized) != 42:
        raise ValueError(
            "Hyperliquid sync expects a 42-character 0x wallet address. "
            "Use the master/sub-account wallet address, not an API wallet."
        )

    return normalized


def _dict_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    return [row for row in value if isinstance(row, dict)]


def _first_number(row: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = _to_float(row.get(key))
        if value is not None:
            return value

    return None


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None