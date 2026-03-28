"""
orders.py
Order placement logic for Binance USDT-M Futures Testnet.

Supports:
  - MARKET orders
  - LIMIT  orders
  - STOP_MARKET orders  (bonus: uses /fapi/v1/algoOrder since Binance API change 2025-12-09)
  - STOP       orders  (bonus: stop-limit, also via algoOrder endpoint)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .client import BinanceFuturesClient, BinanceAPIError, BinanceNetworkError
from .validators import validate_all, ValidationError

logger = logging.getLogger("trading_bot.orders")

ORDER_ENDPOINT = "/fapi/v1/order"
ALGO_ORDER_ENDPOINT = "/fapi/v1/algoOrder"   # Required for conditional orders since 2025-12-09

# Order types that MUST use the Algo endpoint (Binance breaking change 2025-12-09)
ALGO_ORDER_TYPES = {"STOP", "STOP_MARKET", "TAKE_PROFIT", "TAKE_PROFIT_MARKET", "TRAILING_STOP_MARKET"}


# ── Helper ───────────────────────────────────────────────────────────────────

def _build_payload(
    symbol: str,
    side: str,
    order_type: str,
    quantity: str,
    price: Optional[str] = None,
    stop_price: Optional[str] = None,
    time_in_force: str = "GTC",
    reduce_only: bool = False,
) -> Dict[str, Any]:

    if order_type in ALGO_ORDER_TYPES:
        # Algo endpoint uses a different payload shape
        payload: Dict[str, Any] = {
            "symbol":       symbol,
            "side":         side,
            "type":         order_type,
            "orderType":    order_type,
            "algoType":     "CONDITIONAL",
            "quantity":     quantity,
            "triggerPrice": stop_price,
        }
        if order_type == "STOP":          # stop-limit needs a limit price too
            payload["price"] = price
            payload["timeInForce"] = time_in_force
    else:
        # Regular /fapi/v1/order payload shape
        payload = {
            "symbol":   symbol,
            "side":     side,
            "type":     order_type,
            "quantity": quantity,
        }
        if order_type == "LIMIT":
            payload["price"] = price
            payload["timeInForce"] = time_in_force

    if reduce_only:
        payload["reduceOnly"] = "true"

    return payload


def _parse_response(resp: Dict[str, Any]) -> Dict[str, Any]:
    """Handles both regular order and algoOrder response shapes."""
    order = resp.get("order", resp)
    return {
        "orderId":     order.get("orderId") or resp.get("algoId"),
        "symbol":      order.get("symbol"),
        "status":      order.get("status") or resp.get("algoStatus"),
        "side":        order.get("side"),
        "type":        order.get("type") or order.get("orderType"),
        "origQty":     order.get("origQty") or order.get("quantity"),
        "executedQty": order.get("executedQty"),
        "avgPrice":    order.get("avgPrice"),
        "price":       order.get("price"),
        "stopPrice":   order.get("stopPrice") or order.get("triggerPrice"),
        "timeInForce": order.get("timeInForce"),
        "updateTime":  order.get("updateTime"),
    }


# ── Public API ───────────────────────────────────────────────────────────────

class OrderManager:
    """Wraps the BinanceFuturesClient to provide typed order methods."""

    def __init__(self, client: BinanceFuturesClient):
        self.client = client

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float | str,
        price: Optional[float | str] = None,
        stop_price: Optional[float | str] = None,
        time_in_force: str = "GTC",
        reduce_only: bool = False,
    ) -> Dict[str, Any]:
        # 1 – Validate
        params = validate_all(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
        )
        clean_type = params["order_type"]

        # 2 – Choose endpoint
        endpoint = ALGO_ORDER_ENDPOINT if clean_type in ALGO_ORDER_TYPES else ORDER_ENDPOINT
        logger.info(
            "Placing order: symbol=%s side=%s type=%s qty=%s price=%s stop=%s endpoint=%s",
            params["symbol"], params["side"], clean_type,
            params["quantity"], params["price"], params["stop_price"], endpoint,
        )

        # 3 – Build payload
        payload = _build_payload(
            symbol=params["symbol"],
            side=params["side"],
            order_type=clean_type,
            quantity=params["quantity"],
            price=params["price"],
            stop_price=params["stop_price"],
            time_in_force=time_in_force,
            reduce_only=reduce_only,
        )
        logger.debug("Order payload: %s", payload)

        # 4 – Send
        raw = self.client.post(endpoint, params=payload, signed=True)
        result = _parse_response(raw)
        logger.info("Order accepted: orderId=%s status=%s", result["orderId"], result["status"])
        return result

    def market_order(self, symbol: str, side: str, quantity: float | str, **kwargs) -> Dict:
        return self.place_order(symbol, side, "MARKET", quantity, **kwargs)

    def limit_order(self, symbol: str, side: str, quantity: float | str, price: float | str, **kwargs) -> Dict:
        return self.place_order(symbol, side, "LIMIT", quantity, price=price, **kwargs)

    def stop_market_order(self, symbol: str, side: str, quantity: float | str, stop_price: float | str, **kwargs) -> Dict:
        return self.place_order(symbol, side, "STOP_MARKET", quantity, stop_price=stop_price, **kwargs)

    def stop_limit_order(self, symbol: str, side: str, quantity: float | str, price: float | str, stop_price: float | str, **kwargs) -> Dict:
        return self.place_order(symbol, side, "STOP", quantity, price=price, stop_price=stop_price, **kwargs)
