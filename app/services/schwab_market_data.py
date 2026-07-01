from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models.market_data import MarketBar, MarketQuote
from app.services.schwab import SchwabSession
from app.services.market_fetch_specs import SchwabPriceHistorySpec, schwab_price_history_specs


class SchwabMarketDataProvider:
    source = "schwab"

    def __init__(self, session: SchwabSession | None = None) -> None:
        self.session = session or SchwabSession()

    def fetch_quote(self, symbol: str) -> tuple[MarketQuote, Any]:
        clean_symbol = _symbol(symbol)
        payload = self.session.get_equity_quote(clean_symbol)

        quote = MarketQuote(
            symbol=clean_symbol,
            source="schwab",
            fetched_at=datetime.now(timezone.utc),
            bid=_first_number(payload, ("bidPrice", "bid")),
            ask=_first_number(payload, ("askPrice", "ask")),
            last=_first_number(payload, ("lastPrice", "last", "regularMarketLastPrice")),
            mark=_first_number(payload, ("mark", "markPrice")),
            volume=_first_number(payload, ("totalVolume", "volume")),
        )
        return quote, payload

    def fetch_bars(self, symbol: str, *, timeframe: str = "1d") -> tuple[list[MarketBar], Any]:
        clean_symbol = _symbol(symbol)
        request = _schwab_history_request(timeframe)
        payload = self.session.get_price_history(clean_symbol, **request)
        return _bars_from_schwab_payload(clean_symbol, timeframe, payload), payload

    def fetch_bars_for_spec(self, symbol: str, spec: SchwabPriceHistorySpec) -> tuple[list[MarketBar], Any]:
        clean_symbol = _symbol(symbol)
        payload = self.session.get_price_history(
            clean_symbol,
            period_type=spec.period_type,
            period=spec.period,
            frequency_type=spec.frequency_type,
            frequency=spec.frequency,
            need_extended_hours_data=spec.need_extended_hours_data,
        )
        return _bars_from_schwab_payload(clean_symbol, spec.key, payload), payload

    def fetch_all_bars(self, symbol: str) -> list[tuple[SchwabPriceHistorySpec, list[MarketBar], Any, Exception | None]]:
        results: list[tuple[SchwabPriceHistorySpec, list[MarketBar], Any, Exception | None]] = []

        for spec in schwab_price_history_specs():
            try:
                bars, raw_payload = self.fetch_bars_for_spec(symbol, spec)
                results.append((spec, bars, raw_payload, None))
            except Exception as exc:
                results.append((spec, [], None, exc))

        return results


def _schwab_history_request(timeframe: str) -> dict[str, Any]:
    if timeframe == "1d":
        return {
            "period_type": "year",
            "period": 1,
            "frequency_type": "daily",
            "frequency": 1,
            "need_extended_hours_data": False,
        }

    if timeframe == "1m":
        return {
            "period_type": "day",
            "period": 1,
            "frequency_type": "minute",
            "frequency": 1,
            "need_extended_hours_data": True,
        }

    if timeframe == "5m":
        return {
            "period_type": "day",
            "period": 5,
            "frequency_type": "minute",
            "frequency": 5,
            "need_extended_hours_data": True,
        }

    if timeframe == "30m":
        return {
            "period_type": "day",
            "period": 10,
            "frequency_type": "minute",
            "frequency": 30,
            "need_extended_hours_data": True,
        }

    raise ValueError("Unsupported Schwab timeframe. Use one of: 1d, 1m, 5m, 30m.")


def _bars_from_schwab_payload(symbol: str, timeframe: str, payload: Any) -> list[MarketBar]:
    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected Schwab price-history response.")

    raw_candles = payload.get("candles") or []
    if not isinstance(raw_candles, list):
        raise RuntimeError("Unexpected Schwab price-history response: missing candles list.")

    bars: list[MarketBar] = []
    for row in raw_candles:
        if not isinstance(row, dict):
            continue

        try:
            timestamp = datetime.fromtimestamp(int(row["datetime"]) / 1000, tz=timezone.utc)
            bars.append(
                MarketBar(
                    symbol=symbol,
                    source="schwab",
                    timeframe=timeframe,
                    timestamp=timestamp,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume") or 0),
                )
            )
        except (KeyError, TypeError, ValueError, OSError):
            continue

    return sorted(bars, key=lambda bar: bar.timestamp)


def _symbol(value: str) -> str:
    cleaned = value.strip().upper()
    if not cleaned:
        raise ValueError("Symbol is required.")
    return cleaned


def _first_number(row: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = _to_float(row.get(key))
        if value is not None:
            return value
    return None


def _to_float(value: Any) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None
