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
class DatabentoWindowSpec:
    key: str
    lookback_minutes: int


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


def databento_window_specs() -> tuple[DatabentoWindowSpec, ...]:
    return (
        DatabentoWindowSpec("1d", 24 * 60),
        DatabentoWindowSpec("5d", 5 * 24 * 60),
        DatabentoWindowSpec("10d", 10 * 24 * 60),
        DatabentoWindowSpec("30d", 30 * 24 * 60),
        DatabentoWindowSpec("90d", 90 * 24 * 60),
        DatabentoWindowSpec("1y", 366 * 24 * 60),
    )


def databento_resample_frequencies() -> tuple[str, ...]:
    return "1m", "5m", "10m", "15m", "30m", "1h", "1d"
