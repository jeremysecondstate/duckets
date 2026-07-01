from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from app.models.market_data import MarketBar, MarketQuote

DEFAULT_OHLCV_PARQUET_DIR = Path(r"C:\dev\duckets\analysis")


class MarketParquetStore:
    def __init__(self, root_dir: Path | str | None = None) -> None:
        configured = root_dir or os.getenv("DUCKETS_OHLCV_PARQUET_DIR", "").strip()
        self.root_dir = Path(configured) if configured else DEFAULT_OHLCV_PARQUET_DIR
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def save_quote(self, quote: MarketQuote) -> Path:
        return self._write_rows(
            scope="normalized",
            source=quote.source,
            category="quotes",
            symbol=quote.symbol,
            rows=[_quote_row(quote)],
        )

    def save_bars(
        self,
        source: str,
        symbol: str,
        timeframe: str,
        bars: list[MarketBar],
        *,
        request_key: str,
        metadata: dict[str, object] | None = None,
    ) -> Path | None:
        if not bars:
            return None

        extra = dict(metadata or {})
        return self._write_rows(
            scope="normalized",
            source=source,
            category="bars",
            symbol=symbol,
            suffix=request_key,
            rows=[
                {
                    **_bar_row(bar),
                    "request_key": request_key,
                    **extra,
                }
                for bar in bars
            ],
        )

    def save_raw_payload(
        self,
        *,
        source: str,
        category: str,
        symbol: str,
        endpoint: str,
        payload: Any,
    ) -> Path:
        return self._write_rows(
            scope="raw",
            source=source,
            category=category,
            symbol=symbol,
            suffix=endpoint.replace("/", "_"),
            rows=[
                {
                    "symbol": symbol,
                    "source": source,
                    "endpoint": endpoint,
                    "fetched_at": _now_text(),
                    "payload_json": json.dumps(payload, default=str),
                }
            ],
        )

    def save_raw_frame(
        self,
        *,
        source: str,
        category: str,
        symbol: str,
        endpoint: str,
        frame: pd.DataFrame,
    ) -> Path | None:
        if frame.empty:
            return None

        path = self._path(
            scope="raw",
            source=source,
            category=category,
            symbol=symbol,
            suffix=endpoint.replace("/", "_"),
        )
        frame.to_parquet(path, index=False)
        return path

    def save_error(
        self,
        *,
        source: str,
        category: str,
        symbol: str,
        request_key: str,
        error_type: str,
        error_message: str,
        metadata: dict[str, object] | None = None,
    ) -> Path:
        return self._write_rows(
            scope="errors",
            source=source,
            category=category,
            symbol=symbol,
            suffix=request_key,
            rows=[
                {
                    "symbol": symbol,
                    "source": source,
                    "category": category,
                    "request_key": request_key,
                    "fetched_at": _now_text(),
                    "error_type": error_type,
                    "error_message": error_message,
                    **dict(metadata or {}),
                }
            ],
        )

    def _write_rows(
        self,
        *,
        scope: str,
        source: str,
        category: str,
        symbol: str,
        rows: list[dict[str, Any]],
        suffix: str = "",
    ) -> Path:
        path = self._path(scope=scope, source=source, category=category, symbol=symbol, suffix=suffix)
        pd.DataFrame(rows).to_parquet(path, index=False)
        return path

    def _path(self, *, scope: str, source: str, category: str, symbol: str, suffix: str = "") -> Path:
        folder = self.root_dir / scope / source / category
        folder.mkdir(parents=True, exist_ok=True)

        clean_symbol = symbol.strip().upper().replace("/", "-")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        suffix_part = f"_{suffix}" if suffix else ""
        return folder / f"{clean_symbol}{suffix_part}_{timestamp}.parquet"


def _quote_row(quote: MarketQuote) -> dict[str, Any]:
    row = asdict(quote)
    row["fetched_at"] = quote.fetched_at.astimezone(timezone.utc).isoformat()
    return row


def _bar_row(bar: MarketBar) -> dict[str, Any]:
    row = asdict(bar)
    row["timestamp"] = bar.timestamp.astimezone(timezone.utc).isoformat()
    return row


def _now_text() -> str:
    return datetime.now(timezone.utc).isoformat()