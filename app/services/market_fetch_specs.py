from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SchwabPriceHistorySpec:
    key: str
    period_type: str
    period: int
    frequency_type: str
    frequency: int
    need_extended_hours_data: bool = False


@dataclass(frozen=True)
class DatabentoNativeBarSpec:
    key: str
    schema: str
    frequency: str


@dataclass(frozen=True)
class DatabentoDerivedBarSpec:
    key: str
    source_schema: str
    source_frequency: str
    output_frequency: str
    aggregation_method: str


def schwab_price_history_specs() -> tuple[SchwabPriceHistorySpec, ...]:
    specs: list[SchwabPriceHistorySpec] = []

    for period in (1, 2, 3, 4, 5, 10):
        for frequency in (1, 5, 10, 15, 30):
            specs.append(
                SchwabPriceHistorySpec(
                    key=f"day_{period}_minute_{frequency}",
                    period_type="day",
                    period=period,
                    frequency_type="minute",
                    frequency=frequency,
                    need_extended_hours_data=True,
                )
            )

    for period in (1, 2, 3, 6):
        for frequency_type in ("daily", "weekly"):
            specs.append(
                SchwabPriceHistorySpec(
                    key=f"month_{period}_{frequency_type}_1",
                    period_type="month",
                    period=period,
                    frequency_type=frequency_type,
                    frequency=1,
                )
            )

    for period in (1, 2, 3, 5, 10, 15, 20):
        for frequency_type in ("daily", "weekly", "monthly"):
            specs.append(
                SchwabPriceHistorySpec(
                    key=f"year_{period}_{frequency_type}_1",
                    period_type="year",
                    period=period,
                    frequency_type=frequency_type,
                    frequency=1,
                )
            )

    for frequency_type in ("daily", "weekly"):
        specs.append(
            SchwabPriceHistorySpec(
                key=f"ytd_1_{frequency_type}_1",
                period_type="ytd",
                period=1,
                frequency_type=frequency_type,
                frequency=1,
            )
        )

    return tuple(specs)


def databento_native_bar_specs() -> tuple[DatabentoNativeBarSpec, ...]:
    return (
        DatabentoNativeBarSpec("native_1s", "ohlcv-1s", "1s"),
        DatabentoNativeBarSpec("native_1m", "ohlcv-1m", "1m"),
        DatabentoNativeBarSpec("native_1h", "ohlcv-1h", "1h"),
        DatabentoNativeBarSpec("native_1d", "ohlcv-1d", "1d"),
    )


def databento_derived_bar_specs() -> tuple[DatabentoDerivedBarSpec, ...]:
    return (
        DatabentoDerivedBarSpec("derived_5s", "ohlcv-1s", "1s", "5s", "resampled_from_1s"),
        DatabentoDerivedBarSpec("derived_10s", "ohlcv-1s", "1s", "10s", "resampled_from_1s"),
        DatabentoDerivedBarSpec("derived_15s", "ohlcv-1s", "1s", "15s", "resampled_from_1s"),
        DatabentoDerivedBarSpec("derived_30s", "ohlcv-1s", "1s", "30s", "resampled_from_1s"),
        DatabentoDerivedBarSpec("derived_5m", "ohlcv-1m", "1m", "5m", "resampled_from_1m"),
        DatabentoDerivedBarSpec("derived_10m", "ohlcv-1m", "1m", "10m", "resampled_from_1m"),
        DatabentoDerivedBarSpec("derived_15m", "ohlcv-1m", "1m", "15m", "resampled_from_1m"),
        DatabentoDerivedBarSpec("derived_30m", "ohlcv-1m", "1m", "30m", "resampled_from_1m"),
        DatabentoDerivedBarSpec("derived_2h", "ohlcv-1h", "1h", "2h", "resampled_from_1h"),
        DatabentoDerivedBarSpec("derived_4h", "ohlcv-1h", "1h", "4h", "resampled_from_1h"),
        DatabentoDerivedBarSpec("derived_1w", "ohlcv-1d", "1d", "1w", "resampled_from_1d"),
        DatabentoDerivedBarSpec("derived_1mo", "ohlcv-1d", "1d", "1mo", "resampled_from_1d"),
    )
