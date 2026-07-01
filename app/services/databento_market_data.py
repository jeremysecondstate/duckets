from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from app.models.market_data import MarketBar, MarketQuote
from app.services.market_fetch_specs import (
    DatabentoWindowSpec,
    databento_resample_frequencies,
    databento_window_specs,
)

DATABENTO_API_KEY_ENV = "DATABENTO_API_KEY"
DATABENTO_EQUITIES_DATASET_ENV = "DATABENTO_EQUITIES_DATASET"
DATABENTO_EQUITIES_SCHEMA_ENV = "DATABENTO_EQUITIES_SCHEMA"


class DatabentoMarketDataProvider:
    source = "databento"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        dataset: str | None = None,
        schema: str | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv(DATABENTO_API_KEY_ENV, "").strip()
        self.dataset = dataset if dataset is not None else os.getenv(DATABENTO_EQUITIES_DATASET_ENV, "").strip()
        self.schema = schema if schema is not None else os.getenv(DATABENTO_EQUITIES_SCHEMA_ENV, "").strip()

    def fetch_window_frame(
        self,
        symbol: str,
        spec: DatabentoWindowSpec,
        *,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        clean_symbol = _symbol(symbol)
        if not self.api_key:
            raise RuntimeError(f"Missing required environment variable: {DATABENTO_API_KEY_ENV}")
        if not self.dataset:
            raise RuntimeError(f"Missing required environment variable: {DATABENTO_EQUITIES_DATASET_ENV}")
        if not self.schema:
            raise RuntimeError(f"Missing required environment variable: {DATABENTO_EQUITIES_SCHEMA_ENV}")

        import databento as db

        end_time = end or _default_databento_end_time()
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)

        start_time = end_time - timedelta(minutes=spec.lookback_minutes)
        client = db.Historical(self.api_key)

        store = client.timeseries.get_range(
            dataset=self.dataset,
            schema=self.schema,
            symbols=[clean_symbol],
            stype_in="raw_symbol",
            start=start_time.isoformat(),
            end=end_time.isoformat(),
        )

        frame = store.to_df()
        if not isinstance(frame, pd.DataFrame):
            frame = pd.DataFrame(frame)

        return frame.reset_index()

    def fetch_all_bar_frames(
        self,
        symbol: str,
    ) -> list[tuple[DatabentoWindowSpec, pd.DataFrame | None, Exception | None]]:
        results: list[tuple[DatabentoWindowSpec, pd.DataFrame | None, Exception | None]] = []

        for spec in databento_window_specs():
            try:
                results.append((spec, self.fetch_window_frame(symbol, spec), None))
            except Exception as exc:
                results.append((spec, None, exc))

        return results

    def normalized_bars_from_frame(
        self,
        symbol: str,
        frame: pd.DataFrame,
        *,
        window_key: str,
        frequency: str,
    ) -> list[MarketBar]:
        clean_symbol = _symbol(symbol)

        native_bars = _bars_from_databento_frame(clean_symbol, "1m", frame)
        if frequency == "1m":
            return [
                MarketBar(
                    symbol=bar.symbol,
                    source=bar.source,
                    timeframe=f"{window_key}_1m",
                    timestamp=bar.timestamp,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                )
                for bar in native_bars
            ]

        return _resample_bars(clean_symbol, native_bars, window_key=window_key, frequency=frequency)

    def fetch_bars(
        self,
        symbol: str,
        *,
        timeframe: str = "1m",
        lookback_minutes: int = 390,
        end: datetime | None = None,
    ) -> tuple[list[MarketBar], pd.DataFrame]:
        clean_symbol = _symbol(symbol)
        if not self.api_key:
            raise RuntimeError(f"Missing required environment variable: {DATABENTO_API_KEY_ENV}")
        if not self.dataset:
            raise RuntimeError(f"Missing required environment variable: {DATABENTO_EQUITIES_DATASET_ENV}")
        if not self.schema:
            raise RuntimeError(f"Missing required environment variable: {DATABENTO_EQUITIES_SCHEMA_ENV}")

        import databento as db

        end_time = end or _default_databento_end_time()
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)

        start_time = end_time - timedelta(minutes=max(1, lookback_minutes))
        client = db.Historical(self.api_key)

        store = client.timeseries.get_range(
            dataset=self.dataset,
            schema=self.schema,
            symbols=[clean_symbol],
            stype_in="raw_symbol",
            start=start_time.isoformat(),
            end=end_time.isoformat(),
        )

        frame = store.to_df()
        if not isinstance(frame, pd.DataFrame):
            frame = pd.DataFrame(frame)

        raw_frame = frame.reset_index()
        bars = _bars_from_databento_frame(clean_symbol, timeframe, raw_frame)
        return bars, raw_frame

    def fetch_latest_price(
        self,
        symbol: str,
        *,
        lookback_minutes: int = 390,
        end: datetime | None = None,
    ) -> tuple[MarketQuote | None, pd.DataFrame]:
        bars, raw_frame = self.fetch_bars(
            symbol,
            timeframe="1m",
            lookback_minutes=lookback_minutes,
            end=end,
        )

        if not bars:
            return None, raw_frame

        latest = sorted(bars, key=lambda bar: bar.timestamp)[-1]
        return (
            MarketQuote(
                symbol=latest.symbol,
                source="databento",
                fetched_at=datetime.now(timezone.utc),
                last=latest.close,
                volume=latest.volume,
                note="Databento latest price is derived from the latest OHLCV bar close, not bid/ask quote data.",
            ),
            raw_frame,
        )


def _resample_bars(
    symbol: str,
    bars: list[MarketBar],
    *,
    window_key: str,
    frequency: str,
) -> list[MarketBar]:
    if not bars:
        return []

    rule_by_frequency = {
        "5m": "5min",
        "10m": "10min",
        "15m": "15min",
        "30m": "30min",
        "1h": "1h",
        "1d": "1D",
    }
    rule = rule_by_frequency.get(frequency)
    if rule is None:
        raise ValueError(f"Unsupported Databento resample frequency: {frequency}")

    frame = pd.DataFrame(
        [
            {
                "timestamp": bar.timestamp,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
            for bar in bars
        ]
    )

    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame.set_index("timestamp").sort_index()

    resampled = (
        frame.resample(rule)
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .dropna(subset=["open", "high", "low", "close"])
        .reset_index()
    )

    return [
        MarketBar(
            symbol=symbol,
            source="databento",
            timeframe=f"{window_key}_{frequency}",
            timestamp=row["timestamp"].to_pydatetime(),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"] or 0),
        )
        for row in resampled.to_dict(orient="records")
    ]


def _bars_from_databento_frame(symbol: str, timeframe: str, frame: pd.DataFrame) -> list[MarketBar]:
    if frame.empty:
        return []

    bars: list[MarketBar] = []
    for row in frame.to_dict(orient="records"):
        timestamp = _timestamp_from_row(row)
        open_price = _scaled_price(_first_present(row, "open", "open_price", "open_px"))
        high_price = _scaled_price(_first_present(row, "high", "high_price", "high_px"))
        low_price = _scaled_price(_first_present(row, "low", "low_price", "low_px"))
        close_price = _scaled_price(_first_present(row, "close", "close_price", "close_px", "price", "last"))
        volume = _float(_first_present(row, "volume", "size", "qty", "quantity")) or 0.0

        if timestamp is None:
            continue
        if open_price is None or high_price is None or low_price is None or close_price is None:
            continue

        bars.append(
            MarketBar(
                symbol=symbol,
                source="databento",
                timeframe=timeframe,
                timestamp=timestamp,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=volume,
            )
        )

    return sorted(bars, key=lambda bar: bar.timestamp)


def _timestamp_from_row(row: dict[str, Any]) -> datetime | None:
    value = _first_present(row, "ts_event", "ts_recv", "timestamp", "time", "datetime", "index")
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)

    try:
        parsed = pd.Timestamp(value).to_pydatetime()
    except Exception:
        return None

    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _first_present(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def _scaled_price(value: Any) -> float | None:
    price = _float(value)
    if price is None:
        return None

    # Databento normalized prices are often fixed-point nanos.
    if abs(price) >= 10_000_000:
        return price / 1_000_000_000

    return price


def _float(value: Any) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def _default_databento_end_time() -> datetime:
    configured = os.getenv("DATABENTO_EQUITIES_QUERY_END_UTC", "").strip()
    if configured:
        parsed = datetime.fromisoformat(configured.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def _symbol(value: str) -> str:
    cleaned = value.strip().upper()
    if not cleaned:
        raise ValueError("Symbol is required.")
    return cleaned