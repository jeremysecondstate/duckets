from __future__ import annotations

import threading
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from app.models.portfolio import PortfolioSnapshot
from app.services.aggregate import DucketBucketSnapshot
from app.services.hyperliquid import sync_hyperliquid_portfolios
from app.services.schwab import sync_schwab_portfolio

BACKGROUND = "#0b1220"
SURFACE = "#111827"
SURFACE_ALT = "#1f2937"
TEXT = "#e5e7eb"
MUTED_TEXT = "#9ca3af"
ACCENT = "#60a5fa"
BORDER = "#374151"
TABLE_FIELD = "#0f172a"
HEADER_HOVER = "#dbeafe"
HEADER_HOVER_TEXT = "#020617"
SUCCESS = "#22c55e"
DANGER = "#ef4444"


def run_ducket_bucket_ui() -> None:
    root = tk.Tk()
    DucketBucketApp(root)
    root.mainloop()


class DucketBucketApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Duckets")
        self.root.geometry("1180x760")
        self.root.configure(background=BACKGROUND)
        self._apply_theme()

        self._build_layout()

    def _apply_theme(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure(".", background=BACKGROUND, foreground=TEXT, fieldbackground=TABLE_FIELD)
        style.configure("TFrame", background=BACKGROUND)
        style.configure("TLabel", background=BACKGROUND, foreground=TEXT)
        style.configure("TLabelframe", background=BACKGROUND, foreground=TEXT, bordercolor=BORDER)
        style.configure("TLabelframe.Label", background=BACKGROUND, foreground=TEXT)
        style.configure("TButton", background=SURFACE_ALT, foreground=TEXT, bordercolor=BORDER, focusthickness=1)
        style.map(
            "TButton",
            background=[("active", ACCENT), ("disabled", SURFACE)],
            foreground=[("disabled", MUTED_TEXT)],
        )

        style.configure(
            "Summary.TLabelframe",
            background=SURFACE,
            foreground=TEXT,
            bordercolor=BORDER,
        )
        style.configure(
            "Summary.TLabelframe.Label",
            background=SURFACE,
            foreground=TEXT,
        )
        style.configure(
            "Summary.TLabel",
            background=SURFACE,
            foreground=TEXT,
        )

        style.configure(
            "Treeview",
            background=TABLE_FIELD,
            foreground=TEXT,
            fieldbackground=TABLE_FIELD,
            bordercolor=BORDER,
            rowheight=24,
        )
        style.configure(
            "Treeview.Heading",
            background=SURFACE_ALT,
            foreground=TEXT,
            bordercolor=BORDER,
        )
        style.map(
            "Treeview.Heading",
            background=[
                ("active", HEADER_HOVER),
                ("pressed", HEADER_HOVER),
            ],
            foreground=[
                ("active", HEADER_HOVER_TEXT),
                ("pressed", HEADER_HOVER_TEXT),
            ],
        )
        style.map(
            "Treeview",
            background=[("selected", ACCENT)],
            foreground=[("selected", "#020617")],
        )
        style.configure(
            "TNotebook",
            background=BACKGROUND,
            bordercolor=BORDER,
        )
        style.configure(
            "TNotebook.Tab",
            background=SURFACE,
            foreground=TEXT,
            padding=(14, 8),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", SURFACE_ALT), ("active", HEADER_HOVER)],
            foreground=[("selected", TEXT), ("active", HEADER_HOVER_TEXT)],
        )

    def _build_layout(self) -> None:
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True)

        bucket_frame = ttk.Frame(notebook)
        schwab_frame = ttk.Frame(notebook)
        hyperliquid_frame = ttk.Frame(notebook)

        notebook.add(bucket_frame, text="Ducket Bucket")
        notebook.add(schwab_frame, text="Schwab Duckets")
        notebook.add(hyperliquid_frame, text="Hyperliquid Duckets")

        DucketsTab(
            root=self.root,
            parent=bucket_frame,
            title="Ducket Bucket",
            sync_button_text="Sync Bucket",
            sync_snapshots=lambda: [sync_schwab_portfolio(), *sync_hyperliquid_portfolios()],
        )

        DucketsTab(
            root=self.root,
            parent=schwab_frame,
            title="Schwab Duckets",
            sync_button_text="Sync Schwab",
            sync_snapshots=lambda: [sync_schwab_portfolio()],
        )

        DucketsTab(
            root=self.root,
            parent=hyperliquid_frame,
            title="Hyperliquid Duckets",
            sync_button_text="Sync Hyperliquid",
            sync_snapshots=sync_hyperliquid_portfolios,
        )


class DucketsTab:
    def __init__(
        self,
        root: tk.Tk,
        parent: ttk.Frame,
        title: str,
        sync_button_text: str,
        sync_snapshots: Callable[[], list[PortfolioSnapshot]],
    ) -> None:
        self.root = root
        self.sync_snapshots = sync_snapshots

        self.cash_value = tk.StringVar(value="Cash: --")
        self.holdings_value = tk.StringVar(value="Holdings: --")
        self.total_value = tk.StringVar(value="Total: --")
        self.unrealized_pnl = tk.StringVar(value="Unrealized PnL: --")
        self.day_pnl = tk.StringVar(value="Day PnL: --")
        self.status_icon = tk.StringVar(value="❌")

        self.sync_button: ttk.Button | None = None
        self.cash_table: ttk.Treeview | None = None
        self.holdings_table: ttk.Treeview | None = None

        self._build(parent, title, sync_button_text)

    def _build(self, parent: ttk.Frame, title: str, sync_button_text: str) -> None:
        root_frame = ttk.Frame(parent, padding=16)
        root_frame.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(root_frame)
        header.pack(fill=tk.X)

        ttk.Label(header, text=title, font=("Segoe UI", 22, "bold")).pack(side=tk.LEFT)

        self.sync_button = ttk.Button(header, text=sync_button_text, command=self._sync)
        self.sync_button.pack(side=tk.RIGHT)

        ttk.Label(
            header,
            textvariable=self.status_icon,
            font=("Segoe UI", 16, "bold"),
            foreground=DANGER,
        ).pack(side=tk.RIGHT, padx=(0, 10))

        summary = ttk.Frame(root_frame)
        summary.pack(fill=tk.X, pady=(16, 12))

        for label_var in (
            self.cash_value,
            self.holdings_value,
            self.total_value,
            self.unrealized_pnl,
            self.day_pnl,
        ):
            card = ttk.LabelFrame(summary, text="", style="Summary.TLabelframe")
            card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
            ttk.Label(
                card,
                textvariable=label_var,
                font=("Segoe UI", 11, "bold"),
                style="Summary.TLabel",
            ).pack(anchor=tk.W, padx=10, pady=10)

        content_panes = ttk.PanedWindow(root_frame, orient=tk.VERTICAL)
        content_panes.pack(fill=tk.BOTH, expand=True)

        cash_frame = ttk.LabelFrame(content_panes, text="Cash")
        content_panes.add(cash_frame, weight=1)

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

        holdings_frame = ttk.LabelFrame(content_panes, text="Holdings")
        content_panes.add(holdings_frame, weight=4)

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

    def _sync(self) -> None:
        if self.sync_button is not None:
            self.sync_button.configure(state=tk.DISABLED)

        self.status_icon.set("…")

        thread = threading.Thread(target=self._sync_background, daemon=True)
        thread.start()

    def _sync_background(self) -> None:
        try:
            snapshots = self.sync_snapshots()
            bucket = DucketBucketSnapshot(snapshots=snapshots)
        except Exception as exc:
            self.root.after(0, lambda: self._show_error(exc))
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

        self.status_icon.set("✅")

        if self.sync_button is not None:
            self.sync_button.configure(state=tk.NORMAL)

    def _show_error(self, exc: Exception) -> None:
        self.status_icon.set("❌")

        if self.sync_button is not None:
            self.sync_button.configure(state=tk.NORMAL)

        messagebox.showerror("Sync failed", f"{type(exc).__name__}: {exc}")

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

    def _clear_table(self, table: ttk.Treeview | None) -> None:
        if table is None:
            return

        for item_id in table.get_children():
            table.delete(item_id)


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _money_or_dash(value: float | None) -> str:
    return "--" if value is None else _money(value)


def _number(value: float) -> str:
    return f"{value:g}"


def _coverage_or_dash(labels: list[str]) -> str:
    return " + ".join(labels) if labels else "no account day PnL available"