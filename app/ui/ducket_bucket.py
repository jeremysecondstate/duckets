from __future__ import annotations

import threading
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from app.models.portfolio import PortfolioSnapshot
from app.services.aggregate import DucketBucketSnapshot
from app.services.hyperliquid import sync_hyperliquid_portfolios
from app.services.schwab import sync_schwab_portfolio, SchwabSession

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

        SchwabDucketsTab(
            root=self.root,
            parent=schwab_frame,
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


class SchwabDucketsTab(DucketsTab):
    def __init__(self, root: tk.Tk, parent: ttk.Frame) -> None:
        self.order_id = tk.StringVar()
        self.chain_symbol = tk.StringVar()
        self.chain_strikes = tk.StringVar(value="10")

        self.stock_symbol = tk.StringVar()
        self.stock_side = tk.StringVar(value="BUY")
        self.stock_order_type = tk.StringVar(value="LIMIT")
        self.stock_quantity = tk.StringVar()
        self.stock_price = tk.StringVar()

        self.option_symbol = tk.StringVar()
        self.option_side = tk.StringVar(value="BUY_TO_OPEN")
        self.option_order_type = tk.StringVar(value="LIMIT")
        self.option_quantity = tk.StringVar()
        self.option_price = tk.StringVar()

        self.open_orders_table: ttk.Treeview | None = None
        self.recent_orders_table: ttk.Treeview | None = None
        self.option_chain_table: ttk.Treeview | None = None

        super().__init__(
            root=root,
            parent=parent,
            title="Schwab Duckets",
            sync_button_text="Sync Schwab",
            sync_snapshots=lambda: [sync_schwab_portfolio()],
        )

    def _build(self, parent: ttk.Frame, title: str, sync_button_text: str) -> None:
        super()._build(parent, title, sync_button_text)

        actions_frame = ttk.LabelFrame(parent, text="Schwab Order Actions")
        actions_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))

        actions_panes = ttk.PanedWindow(actions_frame, orient=tk.HORIZONTAL)
        actions_panes.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        left_frame = ttk.Frame(actions_panes)
        right_frame = ttk.Frame(actions_panes)

        actions_panes.add(left_frame, weight=2)
        actions_panes.add(right_frame, weight=3)

        self._build_ticket_panel(left_frame)
        self._build_orders_panel(right_frame)
        self._build_option_chain_panel(right_frame)

    def _build_ticket_panel(self, parent: ttk.Frame) -> None:
        stock_frame = ttk.LabelFrame(parent, text="Stock / ETF Ticket")
        stock_frame.pack(fill=tk.X, pady=(0, 10))

        self._entry_row(stock_frame, "Symbol", self.stock_symbol, 0, 0)
        self._combo_row(stock_frame, "Side", self.stock_side, ("BUY", "SELL"), 0, 2)
        self._combo_row(stock_frame, "Order Type", self.stock_order_type, ("LIMIT", "MARKET"), 1, 0)
        self._entry_row(stock_frame, "Quantity", self.stock_quantity, 1, 2)
        self._entry_row(stock_frame, "Limit Price", self.stock_price, 2, 0)

        ttk.Button(stock_frame, text="Submit Stock / ETF Order", command=self._submit_stock_order).grid(
            row=3,
            column=0,
            columnspan=4,
            sticky="ew",
            padx=8,
            pady=8,
        )

        option_frame = ttk.LabelFrame(parent, text="Option Ticket")
        option_frame.pack(fill=tk.X, pady=(0, 10))

        self._entry_row(option_frame, "Option Symbol", self.option_symbol, 0, 0)
        self._combo_row(
            option_frame,
            "Side",
            self.option_side,
            ("BUY_TO_OPEN", "SELL_TO_CLOSE", "SELL_TO_OPEN", "BUY_TO_CLOSE"),
            0,
            2,
        )
        self._combo_row(option_frame, "Order Type", self.option_order_type, ("LIMIT", "MARKET"), 1, 0)
        self._entry_row(option_frame, "Quantity", self.option_quantity, 1, 2)
        self._entry_row(option_frame, "Limit Price", self.option_price, 2, 0)

        ttk.Button(option_frame, text="Submit Option Order", command=self._submit_option_order).grid(
            row=3,
            column=0,
            columnspan=4,
            sticky="ew",
            padx=8,
            pady=8,
        )

        cancel_frame = ttk.LabelFrame(parent, text="Cancel Order")
        cancel_frame.pack(fill=tk.X)

        self._entry_row(cancel_frame, "Order ID", self.order_id, 0, 0)
        ttk.Button(cancel_frame, text="Cancel Order", command=self._cancel_order).grid(
            row=1,
            column=0,
            columnspan=4,
            sticky="ew",
            padx=8,
            pady=8,
        )

    def _build_orders_panel(self, parent: ttk.Frame) -> None:
        orders_frame = ttk.LabelFrame(parent, text="Orders")
        orders_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        button_row = ttk.Frame(orders_frame)
        button_row.pack(fill=tk.X, padx=8, pady=8)

        ttk.Button(button_row, text="Open Orders", command=self._load_open_orders).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(button_row, text="Recent Orders", command=self._load_recent_orders).pack(side=tk.LEFT)

        tables = ttk.PanedWindow(orders_frame, orient=tk.VERTICAL)
        tables.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        open_frame = ttk.LabelFrame(tables, text="Open Orders")
        recent_frame = ttk.LabelFrame(tables, text="Recent Orders")

        tables.add(open_frame, weight=1)
        tables.add(recent_frame, weight=1)

        self.open_orders_table = self._orders_table(open_frame)
        self.recent_orders_table = self._orders_table(recent_frame)

    def _build_option_chain_panel(self, parent: ttk.Frame) -> None:
        chain_frame = ttk.LabelFrame(parent, text="Options Chain")
        chain_frame.pack(fill=tk.BOTH, expand=True)

        input_row = ttk.Frame(chain_frame)
        input_row.pack(fill=tk.X, padx=8, pady=8)

        ttk.Label(input_row, text="Symbol").pack(side=tk.LEFT)
        ttk.Entry(input_row, textvariable=self.chain_symbol, width=12).pack(side=tk.LEFT, padx=(6, 12))

        ttk.Label(input_row, text="Strikes").pack(side=tk.LEFT)
        ttk.Entry(input_row, textvariable=self.chain_strikes, width=8).pack(side=tk.LEFT, padx=(6, 12))

        ttk.Button(input_row, text="Load Options Chain", command=self._load_option_chain).pack(side=tk.LEFT)

        self.option_chain_table = ttk.Treeview(
            chain_frame,
            columns=("symbol", "expiration", "strike", "side", "bid", "ask", "mark"),
            show="headings",
            height=8,
        )
        self._setup_column(self.option_chain_table, "symbol", "Symbol", 220)
        self._setup_column(self.option_chain_table, "expiration", "Expiration", 100)
        self._setup_column(self.option_chain_table, "strike", "Strike", 90, anchor=tk.E)
        self._setup_column(self.option_chain_table, "side", "Side", 70)
        self._setup_column(self.option_chain_table, "bid", "Bid", 90, anchor=tk.E)
        self._setup_column(self.option_chain_table, "ask", "Ask", 90, anchor=tk.E)
        self._setup_column(self.option_chain_table, "mark", "Mark", 90, anchor=tk.E)
        self.option_chain_table.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.option_chain_table.bind("<<TreeviewSelect>>", self._use_selected_option)

    def _orders_table(self, parent: ttk.Frame) -> ttk.Treeview:
        table = ttk.Treeview(
            parent,
            columns=("order_id", "status", "entered", "symbol", "side", "quantity", "price"),
            show="headings",
            height=6,
        )
        self._setup_column(table, "order_id", "Order ID", 120)
        self._setup_column(table, "status", "Status", 100)
        self._setup_column(table, "entered", "Entered", 160)
        self._setup_column(table, "symbol", "Symbol", 120)
        self._setup_column(table, "side", "Side", 120)
        self._setup_column(table, "quantity", "Qty", 80, anchor=tk.E)
        self._setup_column(table, "price", "Price", 100, anchor=tk.E)
        table.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        return table

    def _entry_row(
        self,
        parent: ttk.LabelFrame,
        label: str,
        variable: tk.StringVar,
        row: int,
        column: int,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=column, sticky="w", padx=8, pady=6)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=column + 1, sticky="ew", padx=8, pady=6)
        parent.columnconfigure(column + 1, weight=1)

    def _combo_row(
        self,
        parent: ttk.LabelFrame,
        label: str,
        variable: tk.StringVar,
        values: tuple[str, ...],
        row: int,
        column: int,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=column, sticky="w", padx=8, pady=6)
        ttk.Combobox(parent, textvariable=variable, values=values, state="readonly").grid(
            row=row,
            column=column + 1,
            sticky="ew",
            padx=8,
            pady=6,
        )
        parent.columnconfigure(column + 1, weight=1)

    def _load_open_orders(self) -> None:
        try:
            orders = SchwabSession().get_open_orders()
            self._show_orders(self.open_orders_table, orders)
        except Exception as exc:
            messagebox.showerror("Open orders failed", f"{type(exc).__name__}: {exc}")

    def _load_recent_orders(self) -> None:
        try:
            orders = SchwabSession().get_recent_orders()
            self._show_orders(self.recent_orders_table, orders)
        except Exception as exc:
            messagebox.showerror("Recent orders failed", f"{type(exc).__name__}: {exc}")

    def _load_option_chain(self) -> None:
        try:
            strikes = int(self.chain_strikes.get().strip())
            chain = SchwabSession().get_option_chain(self.chain_symbol.get(), strikes)
            self._show_option_chain(chain)
        except Exception as exc:
            messagebox.showerror("Option chain failed", f"{type(exc).__name__}: {exc}")

    def _cancel_order(self) -> None:
        try:
            result = SchwabSession().cancel_order(self.order_id.get())
            messagebox.showinfo("Cancel order", f"Cancel response: {result}")
        except Exception as exc:
            messagebox.showerror("Cancel order failed", f"{type(exc).__name__}: {exc}")

    def _submit_stock_order(self) -> None:
        try:
            payload = self._stock_order_payload()
            location = SchwabSession().submit_order(payload)
            messagebox.showinfo("Stock / ETF order submitted", f"Location: {location}")
        except Exception as exc:
            messagebox.showerror("Stock / ETF order failed", f"{type(exc).__name__}: {exc}")

    def _submit_option_order(self) -> None:
        try:
            payload = self._option_order_payload()
            location = SchwabSession().submit_order(payload)
            messagebox.showinfo("Option order submitted", f"Location: {location}")
        except Exception as exc:
            messagebox.showerror("Option order failed", f"{type(exc).__name__}: {exc}")

    def _stock_order_payload(self) -> dict[str, object]:
        symbol = self.stock_symbol.get().strip().upper()
        quantity = int(self.stock_quantity.get().strip())
        order_type = self.stock_order_type.get().strip().upper()
        side = self.stock_side.get().strip().upper()

        if not symbol:
            raise ValueError("Stock / ETF symbol is required.")

        payload: dict[str, object] = {
            "orderType": order_type,
            "session": "NORMAL",
            "duration": "DAY",
            "orderStrategyType": "SINGLE",
            "orderLegCollection": [
                {
                    "instruction": side,
                    "quantity": quantity,
                    "instrument": {
                        "symbol": symbol,
                        "assetType": "EQUITY",
                    },
                }
            ],
        }

        if order_type == "LIMIT":
            payload["price"] = self.stock_price.get().strip()

        return payload

    def _option_order_payload(self) -> dict[str, object]:
        symbol = self.option_symbol.get().strip().upper()
        quantity = int(self.option_quantity.get().strip())
        order_type = self.option_order_type.get().strip().upper()
        side = self.option_side.get().strip().upper()

        if not symbol:
            raise ValueError("Option symbol is required.")

        payload: dict[str, object] = {
            "orderType": order_type,
            "session": "NORMAL",
            "duration": "DAY",
            "orderStrategyType": "SINGLE",
            "orderLegCollection": [
                {
                    "instruction": side,
                    "quantity": quantity,
                    "instrument": {
                        "symbol": symbol,
                        "assetType": "OPTION",
                    },
                }
            ],
        }

        if order_type == "LIMIT":
            payload["price"] = self.option_price.get().strip()

        return payload

    def _show_orders(self, table: ttk.Treeview | None, orders: object) -> None:
        if table is None:
            return

        self._clear_table(table)

        if not isinstance(orders, list):
            return

        for order in orders:
            if not isinstance(order, dict):
                continue

            order_id = str(order.get("orderId") or "")
            status = str(order.get("status") or "")
            entered = str(order.get("enteredTime") or "")
            leg = _first_order_leg(order)
            symbol = str(leg.get("symbol") or "")
            side = str(leg.get("instruction") or "")
            quantity = str(leg.get("quantity") or "")
            price = str(order.get("price") or "")

            table.insert(
                "",
                tk.END,
                values=(order_id, status, entered, symbol, side, quantity, price),
            )

    def _show_option_chain(self, chain: object) -> None:
        if self.option_chain_table is None:
            return

        self._clear_table(self.option_chain_table)

        for row in _option_chain_rows(chain):
            self.option_chain_table.insert(
                "",
                tk.END,
                values=(
                    row["symbol"],
                    row["expiration"],
                    row["strike"],
                    row["side"],
                    row["bid"],
                    row["ask"],
                    row["mark"],
                ),
            )

    def _use_selected_option(self, _event: object) -> None:
        if self.option_chain_table is None:
            return

        selected = self.option_chain_table.selection()
        if not selected:
            return

        values = self.option_chain_table.item(selected[0], "values")
        if not values:
            return

        self.option_symbol.set(str(values[0]))


def _first_order_leg(order: dict[str, object]) -> dict[str, object]:
    legs = order.get("orderLegCollection")
    if not isinstance(legs, list) or not legs:
        return {}

    first_leg = legs[0]
    if not isinstance(first_leg, dict):
        return {}

    instrument = first_leg.get("instrument")
    symbol = ""
    if isinstance(instrument, dict):
        symbol = str(instrument.get("symbol") or "")

    return {
        "symbol": symbol,
        "instruction": first_leg.get("instruction"),
        "quantity": first_leg.get("quantity"),
    }


def _option_chain_rows(chain: object) -> list[dict[str, object]]:
    if not isinstance(chain, dict):
        return []

    rows: list[dict[str, object]] = []

    for side, map_name in (("CALL", "callExpDateMap"), ("PUT", "putExpDateMap")):
        exp_map = chain.get(map_name)
        if not isinstance(exp_map, dict):
            continue

        for expiration_key, strikes in exp_map.items():
            expiration = str(expiration_key).split(":", 1)[0]
            if not isinstance(strikes, dict):
                continue

            for strike, contracts in strikes.items():
                if not isinstance(contracts, list):
                    continue

                for contract in contracts:
                    if not isinstance(contract, dict):
                        continue

                    rows.append(
                        {
                            "symbol": contract.get("symbol") or "",
                            "expiration": expiration,
                            "strike": strike,
                            "side": side,
                            "bid": contract.get("bid") or "",
                            "ask": contract.get("ask") or "",
                            "mark": contract.get("mark") or "",
                        }
                    )

    return rows


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _money_or_dash(value: float | None) -> str:
    return "--" if value is None else _money(value)


def _number(value: float) -> str:
    return f"{value:g}"


def _coverage_or_dash(labels: list[str]) -> str:
    return " + ".join(labels) if labels else "no account day PnL available"