from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .client import BinanceAPIError, BinanceFuturesClient
from .validators import OrderRequest, validate_symbol_rules


logger = logging.getLogger("trading_bot.orders")


@dataclass(frozen=True, slots=True)
class OrderResult:
    request_params: dict[str, str]
    response: dict[str, Any]


class OrderService:
    def __init__(self, client: BinanceFuturesClient) -> None:
        self.client = client

    def place_order(self, order_request: OrderRequest) -> OrderResult:
        symbol_info = self.client.get_symbol_info(order_request.symbol)
        validate_symbol_rules(order_request, symbol_info)

        request_params = order_request.to_api_params()
        request_params["newOrderRespType"] = "RESULT"

        response = self.client.place_order(request_params)
        response = self._maybe_enrich_response(
            symbol=order_request.symbol,
            initial_response=response,
        )

        return OrderResult(request_params=request_params, response=response)

    def _maybe_enrich_response(
        self,
        *,
        symbol: str,
        initial_response: dict[str, Any],
    ) -> dict[str, Any]:
        if not self._needs_order_lookup(initial_response):
            return initial_response

        order_id = initial_response.get("orderId")
        if order_id is None:
            return initial_response

        try:
            fetched_order = self.client.get_order(symbol=symbol, order_id=int(order_id))
        except BinanceAPIError:
            logger.warning(
                "Unable to fetch order details after order placement.",
                extra={"event": "order_lookup_failed", "symbol": symbol, "order_id": order_id},
            )
            return initial_response

        return {**initial_response, **fetched_order}

    def _needs_order_lookup(self, response: dict[str, Any]) -> bool:
        required_fields = {"orderId", "status", "executedQty", "avgPrice"}
        return not required_fields.issubset(response.keys())
