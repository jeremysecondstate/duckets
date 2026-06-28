from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import requests

from app.models.portfolio import CashBalance, Holding, PortfolioSnapshot
from app.config import SchwabConfig, schwab_config
from app.services.schwab_token_store import (
    access_token_is_fresh,
    cached_access_token_expires_at,
    load_token_payload,
    refresh_token_is_available,
    save_token_payload,
)

TRADER_BASE_URL = "https://api.schwabapi.com/trader/v1"
MARKETDATA_BASE_URL = "https://api.schwabapi.com/marketdata/v1"
AUTH_URL = "https://api.schwabapi.com/v1/oauth/authorize"
TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"


class SchwabSession:
    def __init__(self, config: SchwabConfig | None = None) -> None:
        self.config = config or schwab_config()
        self.access_token: str | None = None
        self.access_token_expires_at: datetime | None = None
        self.refresh_token: str | None = None
        self.account_hash: str | None = None
        self._hydrate_from_cache()

    def build_authorization_url(self) -> tuple[str, str]:
        state = secrets.token_urlsafe(24)
        params = {
            "response_type": "code",
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "scope": "readonly",
            "state": state,
        }
        return f"{AUTH_URL}?{urlencode(params)}", state

    def exchange_authorization_code(self, authorization_code: str) -> None:
        response = requests.post(
            TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "authorization_code",
                "code": authorization_code.strip(),
                "redirect_uri": self.config.redirect_uri,
            },
            auth=(self.config.client_id, self.config.client_secret),
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        self._store_token_payload(payload, previous_refresh_token=self.refresh_token)

    def ensure_access_token(self) -> None:
        if self._access_token_is_current():
            return

        self.access_token = None
        self.access_token_expires_at = None

        if self.refresh_token:
            self.refresh_access_token()
            return

        raise RuntimeError("Schwab access token is not available. Authorize Schwab first.")

    def refresh_access_token(self) -> None:
        if not self.refresh_token:
            raise RuntimeError("Schwab refresh token is not available.")

        response = requests.post(
            TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
            },
            auth=(self.config.client_id, self.config.client_secret),
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        self._store_token_payload(payload, previous_refresh_token=self.refresh_token)

    def get_account(self) -> Any:
        account_hash = self._get_account_hash()
        response = requests.get(
            f"{TRADER_BASE_URL}/accounts/{account_hash}",
            headers=self._headers(),
            params={"fields": "positions"},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def _get_account_hash(self) -> str:
        if self.account_hash:
            return self.account_hash

        response = requests.get(
            f"{TRADER_BASE_URL}/accounts/accountNumbers",
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()

        accounts = response.json()
        if not isinstance(accounts, list) or not accounts:
            raise RuntimeError("No Schwab accounts returned.")

        account_hash = accounts[0].get("hashValue")
        if not account_hash:
            raise RuntimeError("Schwab account hashValue was missing.")

        self.account_hash = str(account_hash)
        return self.account_hash

    def _headers(self) -> dict[str, str]:
        self.ensure_access_token()
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    def _hydrate_from_cache(self) -> None:
        cached_payload = load_token_payload()
        if not cached_payload:
            return

        if access_token_is_fresh(cached_payload):
            self.access_token = cached_payload.get("access_token")
            self.access_token_expires_at = cached_access_token_expires_at(cached_payload)

        if refresh_token_is_available(cached_payload):
            self.refresh_token = cached_payload.get("refresh_token")

    def _access_token_is_current(self) -> bool:
        if not self.access_token:
            return False

        if self.access_token_expires_at is None:
            return self.refresh_token is None

        return self.access_token_expires_at > datetime.now(timezone.utc)

    def _store_token_payload(self, payload: dict[str, Any], previous_refresh_token: str | None) -> None:
        cached_payload = save_token_payload(payload, previous_refresh_token)
        self.access_token = str(payload["access_token"])
        self.access_token_expires_at = cached_access_token_expires_at(cached_payload)
        self.refresh_token = str(payload.get("refresh_token") or previous_refresh_token or "")

    def get_open_orders(self) -> Any:
        now = datetime.now(timezone.utc)
        return self.get_orders(
            from_entered_time=now - timedelta(days=14),
            to_entered_time=now,
            status="WORKING",
        )

    def get_recent_orders(self) -> Any:
        now = datetime.now(timezone.utc)
        return self.get_orders(
            from_entered_time=now - timedelta(days=14),
            to_entered_time=now,
        )

    def get_orders(
        self,
        *,
        from_entered_time: datetime,
        to_entered_time: datetime,
        status: str | None = None,
    ) -> Any:
        account_hash = self._get_account_hash()
        params = {
            "fromEnteredTime": from_entered_time.astimezone(timezone.utc).isoformat(timespec="seconds"),
            "toEnteredTime": to_entered_time.astimezone(timezone.utc).isoformat(timespec="seconds"),
        }
        if status:
            params["status"] = status

        response = requests.get(
            f"{TRADER_BASE_URL}/accounts/{account_hash}/orders",
            headers=self._headers(),
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def get_option_chain(self, symbol: str, strikes: int) -> Any:
        cleaned_symbol = symbol.strip().upper()
        if not cleaned_symbol:
            raise ValueError("Symbol is required for option chain.")

        response = requests.get(
            f"{MARKETDATA_BASE_URL}/chains",
            headers=self._headers(),
            params={
                "symbol": cleaned_symbol,
                "contractType": "ALL",
                "strikeCount": strikes,
                "includeUnderlyingQuote": "true",
                "strategy": "SINGLE",
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def cancel_order(self, order_id: str) -> object:
        cleaned_order_id = str(order_id).strip()
        if not cleaned_order_id:
            raise ValueError("Order ID is required for cancel.")

        account_hash = self._get_account_hash()
        response = requests.delete(
            f"{TRADER_BASE_URL}/accounts/{account_hash}/orders/{cleaned_order_id}",
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()

        if not response.text:
            return None

        try:
            return response.json()
        except ValueError:
            return response.text

    def submit_order(self, order_payload: dict[str, Any]) -> str | None:
        account_hash = self._get_account_hash()
        response = requests.post(
            f"{TRADER_BASE_URL}/accounts/{account_hash}/orders",
            headers={**self._headers(), "Content-Type": "application/json"},
            json=order_payload,
            timeout=10,
        )
        response.raise_for_status()
        return response.headers.get("Location")


def sync_schwab_portfolio() -> PortfolioSnapshot:
    account_payload = SchwabSession().get_account()
    account = _securities_account(account_payload)
    balances = _current_balances(account)

    holdings = [_holding_from_schwab(row) for row in _position_rows(account)]
    holdings = [holding for holding in holdings if holding is not None]

    holdings_value = round(sum(holding.value for holding in holdings), 2)
    liquidation_value = _first_number(
        balances,
        ("liquidationValue", "currentLiquidationValue", "accountValue"),
    )

    if liquidation_value is not None:
        cash_value = round(liquidation_value - holdings_value, 2)
    else:
        cash_value = round(
            _first_number(
                balances,
                (
                    "cashBalance",
                    "cashAvailableForTrading",
                    "settledCash",
                    "availableFunds",
                    "availableFundsNonMarginableTrade",
                ),
            )
            or 0.0,
            2,
        )

    return PortfolioSnapshot(
        source="schwab",
        account_label="Schwab",
        cash=[
            CashBalance(
                symbol="USD",
                amount=cash_value,
                value=cash_value,
                source="schwab",
                bucket="Cash",
            )
        ],
        holdings=holdings,
        status=f"Schwab synced {_account_label(account)}",
    )


def _securities_account(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected Schwab account response.")

    account = payload.get("securitiesAccount") or payload
    if not isinstance(account, dict):
        raise RuntimeError("Unexpected Schwab account response; missing securitiesAccount.")

    return account


def _current_balances(account: dict[str, Any]) -> dict[str, Any]:
    balances = account.get("currentBalances") or account.get("initialBalances") or {}
    return balances if isinstance(balances, dict) else {}


def _position_rows(account: dict[str, Any]) -> list[dict[str, Any]]:
    positions = account.get("positions") or []
    return [row for row in positions if isinstance(row, dict)] if isinstance(positions, list) else []


def _holding_from_schwab(row: dict[str, Any]) -> Holding | None:
    instrument = row.get("instrument") if isinstance(row.get("instrument"), dict) else {}

    symbol = str(instrument.get("symbol") or row.get("symbol") or "").strip().upper()
    quantity = _net_quantity(row)

    if not symbol or abs(quantity) <= 0.00000001:
        return None

    market_value = _to_float(row.get("marketValue"))
    price = _first_number(row, ("marketPrice", "lastPrice", "currentPrice", "markPrice"))

    if price is None and market_value is not None and abs(quantity) > 0.00000001:
        price = abs(market_value / quantity)

    if market_value is None:
        market_value = quantity * (price or 0.0)

    return Holding(
        symbol=symbol,
        quantity=round(quantity, 8),
        price=round(price or 0.0, 8),
        value=round(market_value, 2),
        source="schwab",
        bucket="Equity",
        unrealized_pnl=_schwab_unrealized_pnl(row),
        day_pnl=_schwab_day_pnl(row),
    )


def _net_quantity(row: dict[str, Any]) -> float:
    long_quantity = _to_float(row.get("longQuantity"))
    short_quantity = _to_float(row.get("shortQuantity"))

    if long_quantity is not None or short_quantity is not None:
        return (long_quantity or 0.0) - (short_quantity or 0.0)

    for key in ("quantity", "settledLongQuantity", "agedQuantity"):
        value = _to_float(row.get(key))
        if value is not None:
            return value

    return 0.0


def _schwab_unrealized_pnl(row: dict[str, Any]) -> float | None:
    long_pnl = _to_float(row.get("longOpenProfitLoss"))
    short_pnl = _to_float(row.get("shortOpenProfitLoss"))

    if long_pnl is not None or short_pnl is not None:
        return round((long_pnl or 0.0) + (short_pnl or 0.0), 2)

    value = _first_number(row, ("openProfitLoss", "unrealizedProfitLoss", "unrealizedPnl"))
    return round(value, 2) if value is not None else None


def _schwab_day_pnl(row: dict[str, Any]) -> float | None:
    value = _first_number(row, ("currentDayProfitLoss", "dayProfitLoss"))

    if value is not None:
        return round(value, 2)

    market_value = _to_float(row.get("marketValue"))
    day_pnl_percent = _first_number(row, ("currentDayProfitLossPercentage", "dayProfitLossPercentage"))

    if market_value is None or day_pnl_percent is None:
        return None

    return round(market_value * (day_pnl_percent / 100.0), 2)


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


def _account_label(account: dict[str, Any]) -> str:
    account_number = str(account.get("accountNumber") or "").strip()
    if account_number:
        return "••••" + account_number[-4:]

    return "account"