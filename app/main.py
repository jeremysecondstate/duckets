from __future__ import annotations

import sys
import argparse

from app.services.aggregate import DucketBucketSnapshot
from app.services.hyperliquid import sync_hyperliquid_portfolios
from app.services.schwab import SchwabSession, sync_schwab_portfolio
from app.ui.ducket_bucket import run_ducket_bucket_ui
from app.services.market_fetch_specs import databento_resample_frequencies

from app.services.databento_market_data import DatabentoMarketDataProvider
from app.services.market_parquet_store import MarketParquetStore
from app.services.schwab_market_data import SchwabMarketDataProvider


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

    if len(sys.argv) > 1 and sys.argv[1] == "ui":
        run_ducket_bucket_ui()
        return

    bucket = DucketBucketSnapshot(
        snapshots=[sync_schwab_portfolio(), *sync_hyperliquid_portfolios()]
    )

    print("DUCKET BUCKET")
    print("=============")
    print(f"Cash: ${bucket.cash_value:,.2f}")
    print(f"Holdings: ${bucket.holdings_value:,.2f}")
    print(f"Total: ${bucket.total_value:,.2f}")
    print(f"Unrealized PnL: {_money_or_dash(bucket.unrealized_pnl)}")
    print(f"Day PnL: {_money_or_dash(bucket.day_pnl)} ({_coverage_or_dash(bucket.day_pnl_accounts)})")

    for snapshot in bucket.snapshots:
        print()
        print(snapshot.account_label.upper())
        print("-" * len(snapshot.account_label))
        print(f"Status: {snapshot.status}")
        print(f"Cash: ${snapshot.cash_value:,.2f}")
        print(f"Holdings: ${snapshot.holdings_value:,.2f}")
        print(f"Total: ${snapshot.total_value:,.2f}")
        print(f"Unrealized PnL: {_money_or_dash(snapshot.unrealized_pnl)}")
        print(f"Day PnL: {_money_or_dash(snapshot.day_pnl)}")

        print()
        print("Cash")
        for cash in snapshot.cash:
            print(f"- {cash.bucket} {cash.symbol}: {cash.amount:g} = ${cash.value:,.2f}")

        print()
        print("Holdings")
        for holding in snapshot.holdings:
            print(
                f"- {holding.bucket} {holding.symbol}: "
                f"{holding.quantity:g} @ ${holding.price:,.4f} = ${holding.value:,.2f}, "
                f"uPnL {_money_or_dash(holding.unrealized_pnl)}, "
                f"day {_money_or_dash(holding.day_pnl)}"
            )


def _money_or_dash(value: float | None) -> str:
    return "--" if value is None else f"${value:,.2f}"


def _coverage_or_dash(labels: list[str]) -> str:
    return " + ".join(labels) if labels else "no account day PnL available"


def _run_market_fetch_all(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(description="Fetch all quote/OHLCV parquet outputs for one symbol.")
    parser.add_argument("symbol")
    parser.add_argument("--source", choices=("schwab", "databento", "both"), default="both")
    args = parser.parse_args(argv)

    symbol = args.symbol.strip().upper()
    store = MarketParquetStore()

    print("MARKET FETCH ALL")
    print("================")
    print(f"Symbol: {symbol}")
    print(f"Source: {args.source}")
    print(f"Output: {store.root_dir}")
    print()

    if args.source in {"schwab", "both"}:
        _fetch_all_schwab_market_data(symbol, store)

    if args.source in {"databento", "both"}:
        _fetch_all_databento_market_data(symbol, store)


def _fetch_all_schwab_market_data(symbol: str, store: MarketParquetStore) -> None:
    provider = SchwabMarketDataProvider()

    print("Schwab quote")
    print("------------")
    try:
        quote, raw_quote = provider.fetch_quote(symbol)
        quote_path = store.save_quote(quote)
        raw_quote_path = store.save_raw_payload(
            source="schwab",
            category="quotes",
            symbol=symbol,
            endpoint="quotes",
            payload=raw_quote,
        )
        print(f"quote: {quote_path}")
        print(f"raw quote: {raw_quote_path}")
    except Exception as exc:
        error_path = store.save_error(
            source="schwab",
            category="quotes",
            symbol=symbol,
            request_key="quotes",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        print(f"quote error: {error_path}")

    print()
    print("Schwab bars")
    print("-----------")

    for spec, bars, raw_payload, exc in provider.fetch_all_bars(symbol):
        metadata = {
            "provider_period_type": spec.period_type,
            "provider_period": spec.period,
            "provider_frequency_type": spec.frequency_type,
            "provider_frequency": spec.frequency,
            "need_extended_hours_data": spec.need_extended_hours_data,
        }

        if exc is not None:
            error_path = store.save_error(
                source="schwab",
                category="bars",
                symbol=symbol,
                request_key=spec.key,
                error_type=type(exc).__name__,
                error_message=str(exc),
                metadata=metadata,
            )
            print(f"{spec.key}: ERROR -> {error_path}")
            continue

        bars_path = store.save_bars(
            "schwab",
            symbol,
            spec.key,
            bars,
            request_key=spec.key,
            metadata=metadata,
        )
        raw_path = store.save_raw_payload(
            source="schwab",
            category="bars",
            symbol=symbol,
            endpoint=f"pricehistory_{spec.key}",
            payload=raw_payload,
        )
        print(f"{spec.key}: {len(bars)} bars -> {bars_path or '--'} | raw -> {raw_path}")


def _fetch_all_databento_market_data(symbol: str, store: MarketParquetStore) -> None:
    provider = DatabentoMarketDataProvider()

    print()
    print("Databento bars")
    print("--------------")

    for window_spec, raw_frame, exc in provider.fetch_all_bar_frames(symbol):
        metadata = {
            "provider_dataset": provider.dataset,
            "provider_schema": provider.schema,
            "lookback_minutes": window_spec.lookback_minutes,
            "window_key": window_spec.key,
        }

        if exc is not None:
            error_path = store.save_error(
                source="databento",
                category="bars",
                symbol=symbol,
                request_key=window_spec.key,
                error_type=type(exc).__name__,
                error_message=str(exc),
                metadata=metadata,
            )
            print(f"{window_spec.key}: ERROR -> {error_path}")
            continue

        if raw_frame is None:
            continue

        raw_path = store.save_raw_frame(
            source="databento",
            category="bars",
            symbol=symbol,
            endpoint=f"{window_spec.key}_native_{provider.dataset}_{provider.schema}",
            frame=raw_frame,
        )
        print(f"{window_spec.key}: raw rows {len(raw_frame)} -> {raw_path or '--'}")

        for frequency in databento_resample_frequencies():
            request_key = f"{window_spec.key}_{frequency}"
            try:
                bars = provider.normalized_bars_from_frame(
                    symbol,
                    raw_frame,
                    window_key=window_spec.key,
                    frequency=frequency,
                )
                bars_path = store.save_bars(
                    "databento",
                    symbol,
                    request_key,
                    bars,
                    request_key=request_key,
                    metadata={**metadata, "output_frequency": frequency},
                )
                print(f"{request_key}: {len(bars)} bars -> {bars_path or '--'}")
            except Exception as frequency_exc:
                error_path = store.save_error(
                    source="databento",
                    category="bars",
                    symbol=symbol,
                    request_key=request_key,
                    error_type=type(frequency_exc).__name__,
                    error_message=str(frequency_exc),
                    metadata={**metadata, "output_frequency": frequency},
                )
                print(f"{request_key}: ERROR -> {error_path}")

    print()
    print("Databento latest-price parquet")
    print("------------------------------")
    try:
        quote, raw_frame = provider.fetch_latest_price(symbol)
        if quote is not None:
            quote_path = store.save_quote(quote)
            print(f"latest price from latest bar close -> {quote_path}")
        else:
            print("latest price unavailable")
    except Exception as exc:
        error_path = store.save_error(
            source="databento",
            category="quotes",
            symbol=symbol,
            request_key="latest_price_from_ohlcv",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        print(f"latest-price error: {error_path}")


if __name__ == "__main__":
    main()