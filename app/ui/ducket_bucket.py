from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable

from app.models.portfolio import PortfolioSnapshot
from app.services.aggregate import DucketBucketSnapshot
from app.services.hyperliquid import sync_hyperliquid_portfolios
from app.services.schwab import sync_schwab_portfolio


def run_ducket_bucket_ui() -> None:
    root = tk.Tk()
    DucketBucketApp(root)
    root.mainloop()


class DucketBucketApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Duckets")
        self.root.geometry("1180x760")

        self.cash_value = tk.StringVar(value="Cash: --")
        self.holdings_value = tk.StringVar(value="Holdings: --")
        self.total_value = tk.StringVar(value="Total: --")
        self.unrealized_pnl = tk.StringVar(value="Unrealized PnL: --")
        self.day_pnl = tk.StringVar(value="Day PnL: --")
        self.status = tk.StringVar(value="Ready.")

        self.sync_button: ttk.Button | None = None
        self.cash_table: ttk.Treeview | None = None
        self.holdings_table: ttk.Treeview | None = None
        self.status_text: tk.Text | None = None

        self._build_layout()

    def _build_layout(self) -> None:
        root_frame = ttk.Frame(self.root, padding=16)
        root_frame.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(root_frame)
        header.pack(fill=tk.X)

        ttk.Label(header, text="Ducket Bucket", font=("Segoe UI", 22, "bold")).pack(side=tk.LEFT)

        self.sync_button = ttk.Button(header, text="Sync Bucket", command=self._sync_bucket)
        self.sync_button.pack(side=tk.RIGHT)

        summary = ttk.Frame(root_frame)
        summary.pack(fill=tk.X, pady=(16, 12))

        for label_var in (
            self.cash_value,
            self.holdings_value,
            self.total_value,
            self.unrealized_pnl,
            self.day_pnl,
        ):
            card = ttk.LabelFrame(summary, text="")
            card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
            ttk.Label(card, textvariable=label_var, font=("Segoe UI", 11, "bold")).pack(anchor=tk.W, padx=10, pady=10)

        ttk.Label(root_frame, textvariable=self.status).pack(anchor=tk.W, pady=(0, 8))

        cash_frame = ttk.LabelFrame(root_frame, text="Cash")
        cash_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 12))

        self.cash_table = ttk.Treeview(
            cash_frame,
            columns=("account", "bucket", "symbol", "amount", "value"),
            show="headings",
            height=6,
        )
        self._setup_column(self.cash_table, "account", "Account", 140)
        self._setup_column(self.cash_table, "bucket", "Bucket", 100)
        self._setup_column(self.cash_table, "symbol", "Symbol", 100)
        self._setup_column(self.cash_table, "amount", "Amount", 140, anchor=tk.E)
        self._setup_column(self.cash_table, "value", "Value", 140, anchor=tk.E)
        self.cash_table.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        holdings_frame = ttk.LabelFrame(root_frame, text="Holdings")
        holdings_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

        self.holdings_table = ttk.Treeview(
            holdings_frame,
            columns=("account", "bucket", "symbol", "quantity", "price", "value", "unrealized_pnl", "day_pnl"),
            show="headings",
            height=14,
        )
        self._setup_column(self.holdings_table, "account", "Account", 140)
        self._setup_column(self.holdings_table, "bucket", "Bucket", 100)
        self._setup_column(self.holdings_table, "symbol", "Symbol", 120)
        self._setup_column(self.holdings_table, "quantity", "Quantity", 110, anchor=tk.E)
        self._setup_column(self.holdings_table, "price", "Price", 110, anchor=tk.E)
        self._setup_column(self.holdings_table, "value", "Value", 120, anchor=tk.E)
        self._setup_column(self.holdings_table, "unrealized_pnl", "Unrealized PnL", 140, anchor=tk.E)
        self._setup_column(self.holdings_table, "day_pnl", "Day PnL", 120, anchor=tk.E)
        self.holdings_table.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        status_frame = ttk.LabelFrame(root_frame, text="Sync Status")
        status_frame.pack(fill=tk.BOTH, expand=False)

        self.status_text = tk.Text(status_frame, height=5, wrap=tk.WORD)
        self.status_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.status_text.insert(tk.END, "Click Sync Bucket to load Schwab, Jeremy, and Alex.\n")
        self.status_text.configure(state=tk.DISABLED)

    def _setup_column(
        self,
        table: ttk.Treeview,
        column: str,
        label: str,
        width: int,
        anchor: str = tk.W,
    ) -> None:
        table.heading(column, text=label)
        table.column(column, width=width, anchor=anchor)

    def _sync_bucket(self) -> None:
        if self.sync_button is not None:
            self.sync_button.configure(state=tk.DISABLED)

        self.status.set("Syncing bucket...")
        self._set_status_text("Syncing Schwab, Jeremy Hyperliquid, and Alex Hyperliquid...\n")

        thread = threading.Thread(target=self._sync_bucket_background, daemon=True)
        thread.start()

    def _sync_bucket_background(self) -> None:
        try:
            bucket = DucketBucketSnapshot(
                snapshots=[sync_schwab_portfolio(), *sync_hyperliquid_portfolios()]
            )
        except Exception as exc:
            self.root.after(0, lambda: self._show_sync_error(exc))
            return

        self.root.after(0, lambda: self._show_bucket(bucket))

    def _show_bucket(self, bucket: DucketBucketSnapshot) -> None:
        self.cash_value.set(f"Cash: {_money(bucket.cash_value)}")
        self.holdings_value.set(f"Holdings: {_money(bucket.holdings_value)}")
        self.total_value.set(f"Total: {_money(bucket.total_value)}")
        self.unrealized_pnl.set(f"Unrealized PnL: {_money_or_dash(bucket.unrealized_pnl)}")
        self.day_pnl.set(
            f"Day PnL: {_money_or_dash(bucket.day_pnl)} ({_coverage_or_dash(bucket.day_pnl_accounts)})"
        )

        self._clear_table(self.cash_table)
        self._clear_table(self.holdings_table)

        for snapshot in bucket.snapshots:
            self._insert_snapshot(snapshot)

        statuses = "\n".join(snapshot.status for snapshot in bucket.snapshots)
        self._set_status_text(statuses + "\n")
        self.status.set("Bucket synced.")

        if self.sync_button is not None:
            self.sync_button.configure(state=tk.NORMAL)

    def _insert_snapshot(self, snapshot: PortfolioSnapshot) -> None:
        if self.cash_table is None or self.holdings_table is None:
            return

        for cash in snapshot.cash:
            self.cash_table.insert(
                "",
                tk.END,
                values=(
                    snapshot.account_label,
                    cash.bucket,
                    cash.symbol,
                    _number(cash.amount),
                    _money(cash.value),
                ),
            )

        for holding in snapshot.holdings:
            self.holdings_table.insert(
                "",
                tk.END,
                values=(
                    snapshot.account_label,
                    holding.bucket,
                    holding.symbol,
                    _number(holding.quantity),
                    _money(holding.price),
                    _money(holding.value),
                    _money_or_dash(holding.unrealized_pnl),
                    _money_or_dash(holding.day_pnl),
                ),
            )

    def _show_sync_error(self, exc: Exception) -> None:
        self.status.set("Sync failed.")
        self._set_status_text(f"{type(exc).__name__}: {exc}\n")

        if self.sync_button is not None:
            self.sync_button.configure(state=tk.NORMAL)

    def _clear_table(self, table: ttk.Treeview | None) -> None:
        if table is None:
            return

        for item_id in table.get_children():
            table.delete(item_id)

    def _set_status_text(self, value: str) -> None:
        if self.status_text is None:
            return

        self.status_text.configure(state=tk.NORMAL)
        self.status_text.delete("1.0", tk.END)
        self.status_text.insert(tk.END, value)
        self.status_text.configure(state=tk.DISABLED)


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _money_or_dash(value: float | None) -> str:
    return "--" if value is None else _money(value)


def _number(value: float) -> str:
    return f"{value:g}"


def _coverage_or_dash(labels: list[str]) -> str:
    return " + ".join(labels) if labels else "no account day PnL available"