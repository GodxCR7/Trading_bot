"""
client.py
Low-level Binance Futures Testnet REST client.

Handles:
  - HMAC-SHA256 request signing
  - Timestamp / recvWindow management
  - HTTP execution with retries
  - Structured logging of every request & response
  - Mapping Binance error codes → readable exceptions
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("trading_bot.client")

TESTNET_BASE_URL = "https://testnet.binancefuture.com"
DEFAULT_RECV_WINDOW = 5000          # ms
DEFAULT_TIMEOUT = 10                # seconds
MAX_RETRIES = 3


# ── Custom Exceptions ────────────────────────────────────────────────────────

class BinanceAPIError(Exception):
    """Raised when Binance returns a non-2xx response or an error payload."""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[Binance {code}] {message}")


class BinanceNetworkError(Exception):
    """Raised on network-level failures (timeout, connection refused, …)."""


# ── Client ───────────────────────────────────────────────────────────────────

class BinanceFuturesClient:
    """
    Minimal Binance USDT-M Futures Testnet client.

    Usage:
        client = BinanceFuturesClient(api_key="…", api_secret="…")
        response = client.post("/fapi/v1/order", params={…}, signed=True)
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = TESTNET_BASE_URL,
        recv_window: int = DEFAULT_RECV_WINDOW,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        if not api_key or not api_secret:
            raise ValueError("api_key and api_secret must not be empty.")

        self.api_key = api_key
        self._api_secret = api_secret.encode()
        self.base_url = base_url.rstrip("/")
        self.recv_window = recv_window
        self.timeout = timeout

        self._session = self._build_session()
        logger.info("BinanceFuturesClient initialised (base_url=%s)", self.base_url)

    # ── Internal helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _build_session() -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=MAX_RETRIES,
            backoff_factor=0.5,
            status_forcelist={429, 500, 502, 503, 504},
            allowed_methods={"GET", "POST", "DELETE"},
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Append recvWindow + timestamp and sign the payload."""
        params["recvWindow"] = self.recv_window
        params["timestamp"] = int(time.time() * 1000)
        query_string = urlencode(params)
        signature = hmac.new(
            self._api_secret,
            query_string.encode(),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    def _headers(self) -> Dict[str, str]:
        return {
            "X-MBX-APIKEY": self.api_key,
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def _execute(
        self,
        method: str,
        endpoint: str,
        params: Dict[str, Any],
        signed: bool,
    ) -> Dict[str, Any]:
        if signed:
            params = self._sign(params)

        url = f"{self.base_url}{endpoint}"

        logger.debug(
            "→ REQUEST  method=%s url=%s params=%s",
            method,
            url,
            {k: v for k, v in params.items() if k != "signature"},
        )

        try:
            if method == "GET":
                resp = self._session.get(url, params=params, headers=self._headers(), timeout=self.timeout)
            elif method == "POST":
                resp = self._session.post(url, data=params, headers=self._headers(), timeout=self.timeout)
            elif method == "DELETE":
                resp = self._session.delete(url, params=params, headers=self._headers(), timeout=self.timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

        except requests.exceptions.Timeout as exc:
            logger.error("Network timeout calling %s %s: %s", method, url, exc)
            raise BinanceNetworkError(f"Request timed out after {self.timeout}s: {exc}") from exc
        except requests.exceptions.ConnectionError as exc:
            logger.error("Connection error calling %s %s: %s", method, url, exc)
            raise BinanceNetworkError(f"Connection error: {exc}") from exc

        logger.debug(
            "← RESPONSE status=%s body=%s",
            resp.status_code,
            resp.text[:500],
        )

        try:
            data = resp.json()
        except ValueError:
            data = {"msg": resp.text, "code": resp.status_code}

        if not resp.ok or (isinstance(data, dict) and "code" in data and data["code"] < 0):
            code = data.get("code", resp.status_code)
            msg = data.get("msg", "Unknown error")
            logger.error("Binance API error code=%s msg=%s", code, msg)
            raise BinanceAPIError(code=code, message=msg)

        logger.info("API call succeeded  endpoint=%s status=%s", endpoint, resp.status_code)
        return data

    # ── Public methods ───────────────────────────────────────────────────────

    def get(self, endpoint: str, params: Optional[Dict] = None, signed: bool = False) -> Any:
        return self._execute("GET", endpoint, params or {}, signed)

    def post(self, endpoint: str, params: Optional[Dict] = None, signed: bool = True) -> Any:
        return self._execute("POST", endpoint, params or {}, signed)

    def delete(self, endpoint: str, params: Optional[Dict] = None, signed: bool = True) -> Any:
        return self._execute("DELETE", endpoint, params or {}, signed)

    def ping(self) -> bool:
        """Return True if the testnet is reachable."""
        try:
            self.get("/fapi/v1/ping")
            logger.info("Ping successful")
            return True
        except (BinanceAPIError, BinanceNetworkError) as exc:
            logger.warning("Ping failed: %s", exc)
            return False

    def get_exchange_info(self) -> Dict:
        return self.get("/fapi/v1/exchangeInfo")

    def get_account(self) -> Dict:
        return self.get("/fapi/v2/account", signed=True)
