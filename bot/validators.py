"""
validators.py
Input validation for order parameters.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Optional


# ── Allowed enum values ──────────────────────────────────────────────────────
VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_MARKET", "STOP"}   # STOP = stop-limit
SYMBOL_RE = re.compile(r"^[A-Z]{2,20}$")


class ValidationError(ValueError):
    """Raised when user-supplied order parameters are invalid."""


def validate_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    if not SYMBOL_RE.match(s):
        raise ValidationError(
            f"Invalid symbol '{symbol}'. Expected uppercase letters only, e.g. BTCUSDT."
        )
    return s


def validate_side(side: str) -> str:
    s = side.strip().upper()
    if s not in VALID_SIDES:
        raise ValidationError(
            f"Invalid side '{side}'. Must be one of: {', '.join(sorted(VALID_SIDES))}."
        )
    return s


def validate_order_type(order_type: str) -> str:
    t = order_type.strip().upper()
    if t not in VALID_ORDER_TYPES:
        raise ValidationError(
            f"Invalid order type '{order_type}'. Must be one of: {', '.join(sorted(VALID_ORDER_TYPES))}."
        )
    return t


def validate_quantity(quantity: str | float) -> str:
    """Return quantity as a clean decimal string."""
    try:
        qty = Decimal(str(quantity))
    except InvalidOperation:
        raise ValidationError(f"Invalid quantity '{quantity}'. Must be a positive number.")
    if qty <= 0:
        raise ValidationError(f"Quantity must be greater than zero, got {quantity}.")
    return str(qty)


def validate_price(price: Optional[str | float], order_type: str) -> Optional[str]:
    """
    Price is required for LIMIT and STOP (stop-limit) orders.
    Returns a clean decimal string or None for MARKET / STOP_MARKET.
    """
    if order_type in {"LIMIT", "STOP"}:
        if price is None:
            raise ValidationError(f"Price is required for {order_type} orders.")
        try:
            p = Decimal(str(price))
        except InvalidOperation:
            raise ValidationError(f"Invalid price '{price}'. Must be a positive number.")
        if p <= 0:
            raise ValidationError(f"Price must be greater than zero, got {price}.")
        return str(p)

    # MARKET / STOP_MARKET — price not required
    if price is not None:
        # Silently ignored, but log a note (caller should handle this)
        pass
    return None


def validate_stop_price(stop_price: Optional[str | float], order_type: str) -> Optional[str]:
    """Stop price is required for STOP and STOP_MARKET orders."""
    if order_type in {"STOP", "STOP_MARKET"}:
        if stop_price is None:
            raise ValidationError(f"--stop-price is required for {order_type} orders.")
        try:
            sp = Decimal(str(stop_price))
        except InvalidOperation:
            raise ValidationError(f"Invalid stop price '{stop_price}'. Must be a positive number.")
        if sp <= 0:
            raise ValidationError(f"Stop price must be greater than zero, got {stop_price}.")
        return str(sp)
    return None


def validate_all(
    symbol: str,
    side: str,
    order_type: str,
    quantity: str | float,
    price: Optional[str | float] = None,
    stop_price: Optional[str | float] = None,
) -> dict:
    """
    Run all validations and return a clean params dict.
    Raises ValidationError on first failure.
    """
    clean_type = validate_order_type(order_type)
    return {
        "symbol": validate_symbol(symbol),
        "side": validate_side(side),
        "order_type": clean_type,
        "quantity": validate_quantity(quantity),
        "price": validate_price(price, clean_type),
        "stop_price": validate_stop_price(stop_price, clean_type),
    }
