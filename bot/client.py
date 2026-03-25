from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any
from urllib.parse import urlencode

import requests


DEFAULT_BASE_URL = "https://testnet.binancefuture.com"


class BinanceClientError(Exception):
    """Base exception for client-related failures."""


class ConfigurationError(BinanceClientError):
    """Raised when required configuration is missing."""


class NetworkError(BinanceClientError):
    """Raised when the HTTP request fails before Binance responds."""


class BinanceAPIError(BinanceClientError):
    """Raised when Binance returns an API error response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        error_code: int | None = None,
        response_body: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.response_body = response_body


class BinanceFuturesClient:
    def __init__(
        self,
        *,
        api_key: str | None,
        api_secret: str | None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 10.0,
        recv_window: int = 5000,
    ) -> None:
        if not api_key or not api_secret:
            raise ConfigurationError(
                "BINANCE_API_KEY and BINANCE_API_SECRET must be set before placing orders."
            )

        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.recv_window = recv_window
        self.logger = logging.getLogger("trading_bot.client")
        self.session = requests.Session()
        self.time_offset_ms: int | None = None
        self.symbol_cache: dict[str, dict[str, Any]] = {}

    def close(self) -> None:
        self.session.close()

    def sync_time(self) -> None:
        payload = self.public_request("GET", "/fapi/v1/time")
        server_time = int(payload["serverTime"])
        local_time = int(time.time() * 1000)
        self.time_offset_ms = server_time - local_time
        self.logger.info(
            "Synchronized Binance server time.",
            extra={
                "event": "time_sync",
                "server_time": server_time,
                "local_time": local_time,
                "time_offset_ms": self.time_offset_ms,
            },
        )

    def public_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request(method=method, path=path, params=params, signed=False)

    def signed_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request(method=method, path=path, params=params, signed=True)

    def get_symbol_info(self, symbol: str) -> dict[str, Any] | None:
        normalized_symbol = symbol.upper()
        if normalized_symbol in self.symbol_cache:
            return self.symbol_cache[normalized_symbol]

        payload = self.public_request("GET", "/fapi/v1/exchangeInfo")
        self.symbol_cache = {
            item["symbol"]: item
            for item in payload.get("symbols", [])
            if "symbol" in item
        }
        return self.symbol_cache.get(normalized_symbol)

    def place_order(self, params: dict[str, Any]) -> dict[str, Any]:
        return self.signed_request("POST", "/fapi/v1/order", params=params)

    def get_order(self, *, symbol: str, order_id: int) -> dict[str, Any]:
        return self.signed_request(
            "GET",
            "/fapi/v1/order",
            params={"symbol": symbol, "orderId": order_id},
        )

    def _request(
        self,
        *,
        method: str,
        path: str,
        params: dict[str, Any] | None,
        signed: bool,
    ) -> dict[str, Any]:
        request_method = method.upper()
        request_params = dict(params or {})
        attempt = 0

        while True:
            if signed:
                if self.time_offset_ms is None:
                    self.sync_time()
                request_params["timestamp"] = self._timestamp_ms()
                request_params["recvWindow"] = self.recv_window
                request_params["signature"] = self._sign(request_params)

            url = f"{self.base_url}{path}"
            self.logger.info(
                "Sending Binance API request.",
                extra={
                    "event": "api_request",
                    "method": request_method,
                    "path": path,
                    "params": self._sanitize_params(request_params),
                },
            )

            try:
                response = self.session.request(
                    request_method,
                    url,
                    params=request_params if request_method == "GET" else None,
                    data=request_params if request_method != "GET" else None,
                    headers=self._headers() if signed else None,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                self.logger.exception(
                    "Network error while calling Binance.",
                    extra={
                        "event": "network_error",
                        "method": request_method,
                        "path": path,
                    },
                )
                raise NetworkError(str(exc)) from exc

            response_payload = self._parse_response_body(response)
            self.logger.info(
                "Received Binance API response.",
                extra={
                    "event": "api_response",
                    "method": request_method,
                    "path": path,
                    "status_code": response.status_code,
                    "body": self._compact_for_log(response_payload),
                },
            )

            if response.ok:
                if isinstance(response_payload, dict):
                    return response_payload
                raise BinanceAPIError(
                    "Binance returned a non-object JSON payload.",
                    status_code=response.status_code,
                    response_body=response_payload,
                )

            api_error = self._build_api_error(response.status_code, response_payload)
            if signed and api_error.error_code == -1021 and attempt == 0:
                self.logger.warning(
                    "Timestamp drift detected, retrying after re-syncing server time.",
                    extra={"event": "timestamp_retry", "path": path},
                )
                self.sync_time()
                attempt += 1
                request_params.pop("signature", None)
                continue

            self.logger.error(
                "Binance API returned an error response.",
                extra={
                    "event": "api_error",
                    "method": request_method,
                    "path": path,
                    "status_code": response.status_code,
                    "error_code": api_error.error_code,
                    "response_body": self._compact_for_log(response_payload),
                },
            )
            raise api_error

    def _headers(self) -> dict[str, str]:
        return {"X-MBX-APIKEY": self.api_key}

    def _sign(self, params: dict[str, Any]) -> str:
        query_string = urlencode(params, doseq=True)
        return hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _timestamp_ms(self) -> int:
        offset = self.time_offset_ms or 0
        return int(time.time() * 1000) + offset

    def _sanitize_params(self, params: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in params.items() if key != "signature"}

    def _parse_response_body(self, response: requests.Response) -> Any:
        if not response.text.strip():
            return {}

        try:
            return response.json()
        except ValueError:
            return response.text

    def _build_api_error(self, status_code: int, response_payload: Any) -> BinanceAPIError:
        if isinstance(response_payload, dict):
            error_code = response_payload.get("code")
            message = response_payload.get("msg", "Unknown Binance API error.")
            return BinanceAPIError(
                f"Binance API error {error_code}: {message}" if error_code is not None else message,
                status_code=status_code,
                error_code=error_code,
                response_body=response_payload,
            )

        return BinanceAPIError(
            f"Unexpected Binance API error: {response_payload}",
            status_code=status_code,
            response_body=response_payload,
        )

    def _compact_for_log(self, payload: Any, *, limit: int = 1500) -> str:
        serialized = json.dumps(payload, default=str, separators=(",", ":"))
        if len(serialized) <= limit:
            return serialized
        return f"{serialized[:limit]}...<truncated>"
