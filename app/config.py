from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


DEFAULT_HYPERLIQUID_INFO_URL = "https://api.hyperliquid.xyz/info"


load_dotenv()


@dataclass(frozen=True)
class HyperliquidAccountConfig:
    label: str
    wallet_address: str


def hyperliquid_accounts() -> list[HyperliquidAccountConfig]:
    return [
        HyperliquidAccountConfig(
            label="Jeremy",
            wallet_address=_required_env("HYPE_WALLET_ADDRESS_JEREMY_SECONDSTATE"),
        ),
        HyperliquidAccountConfig(
            label="Alex",
            wallet_address=_required_env("HYPE_WALLET_ADDRESS_ALEX_SECONDSTATE"),
        ),
    ]


def hyperliquid_info_url() -> str:
    return os.getenv("HYPERLIQUID_INFO_URL", DEFAULT_HYPERLIQUID_INFO_URL).strip()


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value