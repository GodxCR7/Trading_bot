#  Binance Futures Testnet Trading Bot

A clean, production-grade Python CLI for placing orders on **Binance USDT-M Futures Testnet**.

---

## ✨ Features

| Feature | Details |
|---|---|
| **Order types** | MARKET, LIMIT, STOP_MARKET (bonus) |
| **Sides** | BUY & SELL |
| **CLI** | Typer + Rich — coloured tables, validation feedback |
| **Logging** | Rotating file logger (DEBUG) + console (WARNING), logs all API requests & responses |
| **Error handling** | Validation errors, Binance API errors, network failures — all caught cleanly |
| **Config** | `.env` file or env vars — no hardcoded secrets |

---

##  Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py
│   ├── client.py          # Binance REST client (HMAC signing, retries, logging)
│   ├── orders.py          # Order placement logic
│   ├── validators.py      # Input validation
│   └── logging_config.py  # Rotating file + console logging setup
├── cli.py                 # CLI entry point (Typer)
├── sample_logs/           # Real log files from testnet runs
│   ├── market_order.log
│   ├── limit_order.log
│   └── stop_market_order.log
├── logs/                  # Runtime logs (auto-created on first run)
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

##  Setup

### 1 — Prerequisites

- Python **3.9+**
- A **Binance Futures Testnet** account → https://testnet.binancefuture.com

### 2 — Clone & install

```bash
git clone https://github.com/<your-username>/trading-bot.git
cd trading-bot

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 3 — Configure credentials

```bash
# Linux/Mac
cp .env.example .env

# Windows
copy .env.example .env
```

Edit `.env`:
```
BINANCE_API_KEY=your_testnet_api_key_here
BINANCE_API_SECRET=your_testnet_api_secret_here
```

> **How to get testnet keys**
> 1. Go to https://testnet.binancefuture.com
> 2. Log in (GitHub OAuth)
> 3. Click **API Management** → Generate a key pair
> 4. Paste them into `.env`

---

## 🚀 How to Run

### Check connectivity

```bash
python cli.py ping
```

### View account balances

```bash
python cli.py account
```

### Place a MARKET order

```bash
# Buy 0.01 BTC at market price
python cli.py place-order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01
```

### Place a LIMIT order

```bash
# Sell 0.01 BTC at $99,000
python cli.py place-order --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.01 --price 99000
```

### Place a STOP_MARKET order *(bonus)*

```bash
# Sell 0.1 BTC if price drops to $50,000 (must have an open long position)
python cli.py place-order --symbol BTCUSDT --side SELL --type STOP_MARKET --quantity 0.1 --stop-price 50000 --reduce-only
```

> **Note:** STOP_MARKET orders require an existing open position and use the
> `/fapi/v1/algoOrder` endpoint (Binance API change, Dec 2025).
> The `--stop-price` must be **below** current market price for a SELL stop.

### Pass credentials inline (no .env needed)

```bash
python cli.py place-order \
  --api-key YOUR_KEY \
  --api-secret YOUR_SECRET \
  --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01
```

### Full help

```bash
python cli.py --help
python cli.py place-order --help
```

---

##  Sample Output

```
   Order Request Summary
  Parameter       Value
 ━━━━━━━━━━━━━━━━━━━━━━━━━
  Symbol          BTCUSDT
  Side            SELL
  Type            LIMIT
  Quantity        0.01
  Price           99000.0
  Time-In-Force   GTC
  Reduce Only     False

        ORDER ACCEPTED
╭───────────────┬─────────────╮
│ Field         │ Value       │
├───────────────┼─────────────┤
│ Order ID      │ 13001493119 │
│ Symbol        │ BTCUSDT     │
│ Status        │ NEW         │
│ Side          │ SELL        │
│ Type          │ LIMIT       │
│ Orig Qty      │ 0.010       │
│ Limit Price   │ 99000.00    │
│ Time-In-Force │ GTC         │
╰───────────────┴─────────────╯

╭──────────────────────────────────╮
│   Order placed successfully!     │
╰──────────────────────────────────╯
```

---

##  Logging

All activity is logged to `logs/trading_bot.log` (auto-created on first run).

- **File handler** — DEBUG level: every request payload, response body, errors
- **Console handler** — WARNING+ only (keeps terminal clean)
- **Rotating**: max 5 MB per file, 3 backups kept

Sample log lines:
```
2025-03-28T10:31:07 | INFO  | trading_bot.orders | Placing order: symbol=BTCUSDT side=SELL type=LIMIT qty=0.01 price=99000 endpoint=/fapi/v1/order
2025-03-28T10:31:07 | DEBUG | trading_bot.client | → REQUEST  method=POST url=.../fapi/v1/order params={...}
2025-03-28T10:31:07 | DEBUG | trading_bot.client | ← RESPONSE status=200 body={...}
2025-03-28T10:31:07 | INFO  | trading_bot.orders | Order accepted: orderId=13001493119 status=NEW
```

Real sample logs are in `sample_logs/`.

---

##  Error Handling

| Scenario | Behaviour |
|---|---|
| Missing price for LIMIT order | `ValidationError` — clear message, exit 2 |
| Invalid symbol / side / type | `ValidationError` — caught before any API call |
| Binance rejects order (e.g. insufficient margin) | `BinanceAPIError` with code + message, exit 3 |
| Network timeout / connection refused | `BinanceNetworkError`, exit 4 |
| Missing API credentials | Descriptive error, exit 1 |

---

##  Assumptions

- Only **USDT-M Futures Testnet** is supported (base URL: `https://testnet.binancefuture.com`).
- `positionSide` defaults to `BOTH` (one-way mode). Hedge-mode accounts are not tested.
- `timeInForce` defaults to `GTC` for LIMIT orders; override with `--tif IOC` or `--tif FOK`.
- Quantity precision is passed as-is — Binance will reject orders that violate the symbol's `LOT_SIZE` filter.
- **STOP_MARKET orders** require an open position (`--reduce-only`) and are routed to `/fapi/v1/algoOrder` with `algoType=CONDITIONAL` and `triggerPrice` — this is a Binance breaking API change from December 2025.
- The bot does **not** manage open positions or cancel orders — it is a pure order-placement tool.

---

##  Dependencies

```
requests>=2.31.0       # HTTP client with retry adapter
typer[all]>=0.12.0     # CLI framework (includes click)
rich>=13.7.0           # Terminal formatting
python-dotenv>=1.0.0   # .env file loading
```

Install: `pip install -r requirements.txt`
