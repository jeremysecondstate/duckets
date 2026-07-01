from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

import pandas as pd

from app.models.market_data import MarketBar, MarketQuote
from app.services.market_fetch_specs import (
    DatabentoDerivedBarSpec,
    DatabentoNativeBarSpec,
    databento_derived_bar_specs,
    databento_native_bar_specs,
)

DATABENTO_API_KEY_ENV = "DATABENTO_API_KEY"
DATABENTO_EQUITIES_DATASET_ENV = "DATABENTO_EQUITIES_DATASET"
DATABENTO_EQUITIES_SCHEMA_ENV = "DATABENTO_EQUITIES_SCHEMA"
DATABENTO_EQUITIES_NATIVE_SCHEMAS_ENV = "DATABENTO_EQUITIES_NATIVE_SCHEMAS"

DEFAULT_DATABENTO_NATIVE_SCHEMAS = ("ohlcv-1s", "ohlcv-1m", "ohlcv-1h", "ohlcv-1d")


@dataclass(frozen=True)
class DatabentoAvailableRange:
    schema: str
    start: datetime
    end: datetime


class DatabentoMarketDataProvider:
    source = "databento"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        dataset: str | None = None,
        schema: str | None = None,
        native_schemas: tuple[str, ...] | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv(DATABENTO_API_KEY_ENV, "").strip()
        self.dataset = dataset if dataset is not None else os.getenv(DATABENTO_EQUITIES_DATASET_ENV, "").strip()
        self.schema = schema if schema is not None else os.getenv(DATABENTO_EQUITIES_SCHEMA_ENV, "").strip()
        self.native_schemas = native_schemas if native_schemas is not None else _configured_native_schemas()

    def native_specs(self) -> tuple[DatabentoNativeBarSpec, ...]:
        allowed = set(self.native_schemas)
        return tuple(spec for spec in databento_native_bar_specs() if spec.schema in allowed)

    def derived_specs(self) -> tuple[DatabentoDerivedBarSpec, ...]:
        allowed = set(self.native_schemas)
        return tuple(spec for spec in databento_derived_bar_specs() if spec.source_schema in allowed)

    def dataset_range(self) -> Mapping[str, Any]:
        self._validate_config()
        client = self._client()
        payload = client.metadata.get_dataset_range(dataset=self.dataset)
        if not isinstance(payload, Mapping):
            raise RuntimeError("Databento get_dataset_range returned an unexpected response.")
        return payload

    def available_range_for_schema(
        self,
        schema: str,
        *,
        dataset_range: Mapping[str, Any] | None = None,
    ) -> DatabentoAvailableRange:
        payload = dataset_range if dataset_range is not None else self.dataset_range()
        schema_payload = payload.get("schema")
        if isinstance(schema_payload, Mapping):
            selected = schema_payload.get(schema)
            if isinstance(selected, Mapping):
                start = _datetime_from_value(selected.get("start"))
                end = _datetime_from_value(selected.get("end"))
                if start is not None and end is not None:
                    return DatabentoAvailableRange(schema=schema, start=start, end=end)

        start = _datetime_from_value(payload.get("start"))
        end = _datetime_from_value(payload.get("end"))
        if start is not None and end is not None:
            return DatabentoAvailableRange(schema=schema, start=start, end=end)

        raise RuntimeError(f"Databento availability range was missing for schema {schema}.")

    def fetch_native_bars(
        self,
        symbol: str,
        spec: DatabentoNativeBarSpec,
        *,
        available_range: DatabentoAvailableRange | None = None,
    ) -> tuple[list[MarketBar], pd.DataFrame, DatabentoAvailableRange]:
        clean_symbol = _symbol(symbol)
        self._validate_config()
        selected_range = available_range or self.available_range_for_schema(spec.schema)
        client = self._client()

        store = client.timeseries.get_range(
            dataset=self.dataset,
            schema=spec.schema,
            symbols=[clean_symbol],
            stype_in="raw_symbol",
            start=selected_range.start.isoformat(),
            end=selected_range.end.isoformat(),
        )

        frame = store.to_df()
        if not isinstance(frame, pd.DataFrame):
            frame = pd.DataFrame(frame)

        raw_frame = frame.reset_index()
        bars = _bars_from_databento_frame(clean_symbol, spec.frequency, raw_frame)
        return bars, raw_frame, selected_range

    def fetch_all_native_bars(
        self,
        symbol: str,
    ) -> list[tuple[DatabentoNativeBarSpec, list[MarketBar], pd.DataFrame | None, DatabentoAvailableRange | None, Exception | None]]:
        results: list[tuple[DatabentoNativeBarSpec, list[MarketBar], pd.DataFrame | None, DatabentoAvailableRange | None, Exception | None]] = []
        try:
            range_payload = self.dataset_range()
        except Exception as exc:
            return [(spec, [], None, None, exc) for spec in self.native_specs()]

        for spec in self.native_specs():
            try:
                available_range = self.available_range_for_schema(spec.schema, dataset_range=range_payload)
                bars, raw_frame, selected_range = self.fetch_native_bars(symbol, spec, available_range=available_range)
                results.append((spec, bars, raw_frame, selected_range, None))
            except Exception as exc:
                results.append((spec, [], None, None, exc))

        return results

    def derive_bars(
        self,
        symbol: str,
        source_bars: list[MarketBar],
        spec: DatabentoDerivedBarSpec,
    ) -> list[MarketBar]:
        clean_symbol = _symbol(symbol)
        return _resample_bars(clean_symbol, source_bars, frequency=spec.output_frequency)

    def quote_from_latest_bar(self, symbol: str, bars: list[MarketBar]) -> MarketQuote | None:
        clean_symbol = _symbol(symbol)
        if not bars:
            return None

        latest = max(bars, key=lambda bar: bar.timestamp)
        return MarketQuote(
            symbol=clean_symbol,
            source="databento",
            fetched_at=datetime.now(timezone.utc),
            last=latest.close,
            volume=latest.volume,
            note=(
                f"Databento latest price is derived from the latest native OHLCV bar close "
                f"({latest.timeframe} at {latest.timestamp.isoformat()}), not bid/ask quote data."
            ),
        )

    def _client(self) -> Any:
        import databento as db

        return db.Historical(self.api_key)

    def _validate_config(self) -> None:
        if not self.api_key:
            raise RuntimeError(f"Missing required environment variable: {DATABENTO_API_KEY_ENV}")
        if not self.dataset:
            raise RuntimeError(f"Missing required environment variable: {DATABENTO_EQUITIES_DATASET_ENV}")
        if not self.native_schemas:
            fallback = self.schema or ""
            if not fallback:
                raise RuntimeError(f"Missing required environment variable: {DATABENTO_EQUITIES_NATIVE_SCHEMAS_ENV}")


def _resample_bars(
    symbol: str,
    bars: list[MarketBar],
    *,
    frequency: str,
) -> list[MarketBar]:
    if not bars:
        return []

    rule_by_frequency = {
        "5s": "5s",
        "10s": "10s",
        "15s": "15s",
        "30s": "30s",
        "5m": "5min",
        "10m": "10min",
        "15m": "15min",
        "30m": "30min",
        "2h": "2h",
        "4h": "4h",
        "1w": "W-FRI",
        "1mo": "MS",
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
            timeframe=frequency,
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

    return _datetime_from_value(value)


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


def _datetime_from_value(value: Any) -> datetime | None:
    if value in (None, ""):
        return None

    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)

    try:
        parsed = pd.Timestamp(value).to_pydatetime()
    except Exception:
        return None

    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _configured_native_schemas() -> tuple[str, ...]:
    configured = os.getenv(DATABENTO_EQUITIES_NATIVE_SCHEMAS_ENV, "").strip()
    if not configured:
        legacy_schema = os.getenv(DATABENTO_EQUITIES_SCHEMA_ENV, "").strip()
        return (legacy_schema,) if legacy_schema else DEFAULT_DATABENTO_NATIVE_SCHEMAS

    schemas = tuple(
        schema.strip()
        for schema in configured.split(",")
        if schema.strip()
    )
    return schemas or DEFAULT_DATABENTO_NATIVE_SCHEMAS


def _symbol(value: str) -> str:
    cleaned = value.strip().upper()
    if not cleaned:
        raise ValueError("Symbol is required.")
    return cleaned
