"""
cli.py
CLI entry point for the Binance Futures Testnet trading bot.

Usage examples:
    python cli.py place-order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01
    python cli.py place-order --symbol BTCUSDT --side BUY --type LIMIT  --quantity 0.01 --price 60000
    python cli.py place-order --symbol ETHUSDT --side SELL --type STOP_MARKET --quantity 0.1 --stop-price 2900
    python cli.py place-order --symbol BTCUSDT --side BUY  --type STOP  --quantity 0.01 --price 61000 --stop-price 60500
    python cli.py ping
    python cli.py account
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from dotenv import load_dotenv

# ── Bootstrap: make sure project root is on sys.path ────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from bot.logging_config import setup_logging
from bot.client import BinanceFuturesClient, BinanceAPIError, BinanceNetworkError
from bot.orders import OrderManager
from bot.validators import ValidationError

# ── Load .env (optional) ─────────────────────────────────────────────────────
load_dotenv(ROOT / ".env")

# ── Logging & Rich console ───────────────────────────────────────────────────
logger = setup_logging()
console = Console()
err_console = Console(stderr=True, style="bold red")

# ── Typer app ─────────────────────────────────────────────────────────────────
app = typer.Typer(
    name="trading-bot",
    help="Binance Futures Testnet trading bot – place MARKET, LIMIT, STOP_MARKET, or STOP-LIMIT orders.",
    add_completion=False,
)


# ── Helper: build client from env / options ───────────────────────────────────
def _make_client(api_key: Optional[str], api_secret: Optional[str]) -> BinanceFuturesClient:
    key = api_key or os.getenv("BINANCE_API_KEY", "")
    secret = api_secret or os.getenv("BINANCE_API_SECRET", "")
    if not key or not secret:
        err_console.print(
            "[bold red]ERROR:[/bold red] API key and secret are required.\n"
            "Set BINANCE_API_KEY and BINANCE_API_SECRET in your .env file "
            "or pass --api-key / --api-secret on the command line."
        )
        raise typer.Exit(code=1)
    return BinanceFuturesClient(api_key=key, api_secret=secret)


# ── Helper: pretty-print order result ────────────────────────────────────────
def _print_order_result(result: dict, success: bool = True):
    status_color = "green" if success else "red"
    status_label = "✅  ORDER ACCEPTED" if success else "❌  ORDER FAILED"

    table = Table(title=status_label, box=box.ROUNDED, title_style=f"bold {status_color}")
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    fields = [
        ("Order ID",      "orderId"),
        ("Symbol",        "symbol"),
        ("Status",        "status"),
        ("Side",          "side"),
        ("Type",          "type"),
        ("Orig Qty",      "origQty"),
        ("Executed Qty",  "executedQty"),
        ("Avg Price",     "avgPrice"),
        ("Limit Price",   "price"),
        ("Stop Price",    "stopPrice"),
        ("Time-In-Force", "timeInForce"),
    ]
    for label, key in fields:
        val = result.get(key)
        if val is not None and val != "" and val != "0":
            table.add_row(label, str(val))

    console.print(table)


# ── place-order command ───────────────────────────────────────────────────────
@app.command("place-order")
def place_order(
    symbol: str = typer.Option(..., "--symbol", "-s",        help="Trading pair, e.g. BTCUSDT"),
    side:   str = typer.Option(..., "--side",                help="BUY or SELL"),
    order_type: str = typer.Option(..., "--type", "-t",      help="MARKET | LIMIT | STOP_MARKET | STOP"),
    quantity: float = typer.Option(..., "--quantity", "-q",  help="Order quantity"),
    price:  Optional[float] = typer.Option(None, "--price", "-p",      help="Limit price (required for LIMIT / STOP)"),
    stop_price: Optional[float] = typer.Option(None, "--stop-price",   help="Stop trigger price (required for STOP_MARKET / STOP)"),
    reduce_only: bool = typer.Option(False, "--reduce-only",            help="Reduce-only flag"),
    time_in_force: str = typer.Option("GTC", "--tif",                  help="Time-in-force: GTC | IOC | FOK (LIMIT orders)"),
    api_key: Optional[str] = typer.Option(None, "--api-key",           help="Binance API key (or set BINANCE_API_KEY env var)", envvar="BINANCE_API_KEY"),
    api_secret: Optional[str] = typer.Option(None, "--api-secret",     help="Binance API secret (or set BINANCE_API_SECRET env var)", envvar="BINANCE_API_SECRET"),
):
    """Place a futures order on Binance Testnet."""

    # ── Print request summary ────────────────────────────────────────────────
    summary = Table(title="📋  Order Request Summary", box=box.SIMPLE_HEAVY, title_style="bold blue")
    summary.add_column("Parameter", style="cyan")
    summary.add_column("Value",     style="yellow")
    summary.add_row("Symbol",     symbol.upper())
    summary.add_row("Side",       side.upper())
    summary.add_row("Type",       order_type.upper())
    summary.add_row("Quantity",   str(quantity))
    if price is not None:
        summary.add_row("Price",  str(price))
    if stop_price is not None:
        summary.add_row("Stop Price", str(stop_price))
    if order_type.upper() == "LIMIT":
        summary.add_row("Time-In-Force", time_in_force)
    summary.add_row("Reduce Only", str(reduce_only))
    console.print(summary)

    # ── Execute ──────────────────────────────────────────────────────────────
    try:
        client = _make_client(api_key, api_secret)
        manager = OrderManager(client)
        result = manager.place_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            time_in_force=time_in_force,
            reduce_only=reduce_only,
        )
        _print_order_result(result, success=True)
        console.print(Panel("[bold green]✅ Order placed successfully![/bold green]", border_style="green"))
        logger.info("CLI: order placed successfully orderId=%s", result.get("orderId"))

    except ValidationError as exc:
        err_console.print(f"\n[bold red]Validation Error:[/bold red] {exc}")
        logger.warning("Validation error: %s", exc)
        raise typer.Exit(code=2)

    except BinanceAPIError as exc:
        err_console.print(f"\n[bold red]Binance API Error [{exc.code}]:[/bold red] {exc.message}")
        logger.error("Binance API error: code=%s msg=%s", exc.code, exc.message)
        raise typer.Exit(code=3)

    except BinanceNetworkError as exc:
        err_console.print(f"\n[bold red]Network Error:[/bold red] {exc}")
        logger.error("Network error: %s", exc)
        raise typer.Exit(code=4)


# ── ping command ──────────────────────────────────────────────────────────────
@app.command("ping")
def ping(
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="BINANCE_API_KEY"),
    api_secret: Optional[str] = typer.Option(None, "--api-secret", envvar="BINANCE_API_SECRET"),
):
    """Check connectivity to Binance Futures Testnet."""
    try:
        client = _make_client(api_key, api_secret)
        if client.ping():
            console.print(Panel("[bold green]✅ Testnet is reachable![/bold green]", border_style="green"))
        else:
            err_console.print("Testnet ping failed.")
            raise typer.Exit(code=1)
    except (BinanceAPIError, BinanceNetworkError) as exc:
        err_console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)


# ── account command ───────────────────────────────────────────────────────────
@app.command("account")
def account(
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="BINANCE_API_KEY"),
    api_secret: Optional[str] = typer.Option(None, "--api-secret", envvar="BINANCE_API_SECRET"),
):
    """Fetch and display your Binance Futures Testnet account summary."""
    try:
        client = _make_client(api_key, api_secret)
        info = client.get_account()

        table = Table(title="💼  Account Summary", box=box.ROUNDED, title_style="bold magenta")
        table.add_column("Asset", style="cyan")
        table.add_column("Wallet Balance", style="green")
        table.add_column("Unrealized PnL", style="yellow")
        table.add_column("Available Balance", style="white")

        for asset in info.get("assets", []):
            if float(asset.get("walletBalance", 0)) > 0:
                table.add_row(
                    asset.get("asset", ""),
                    asset.get("walletBalance", "0"),
                    asset.get("unrealizedProfit", "0"),
                    asset.get("availableBalance", "0"),
                )
        console.print(table)

    except (BinanceAPIError, BinanceNetworkError) as exc:
        err_console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app()
