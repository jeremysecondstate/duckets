from __future__ import annotations

import os

from dotenv import load_dotenv


DEFAULT_HYPERLIQUID_INFO_URL = "https://api.hyperliquid.xyz/info"


load_dotenv()


def hyperliquid_wallet_address() -> str:
    return _required_env("HYPE_WALLET_ADDRESS_JEREMY")


def hyperliquid_info_url() -> str:
    return os.getenv("HYPERLIQUID_INFO_URL", DEFAULT_HYPERLIQUID_INFO_URL).strip()


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value