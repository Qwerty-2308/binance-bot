from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_MARKET"}
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{5,20}$")


class ValidationError(ValueError):
    """Raised when CLI input is invalid before calling Binance."""


@dataclass(frozen=True, slots=True)
class OrderRequest:
    symbol: str
    side: str
    order_type: str
    quantity: Decimal
    price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: str | None = None

    def to_api_params(self) -> dict[str, str]:
        params = {
            "symbol": self.symbol,
            "side": self.side,
            "type": self.order_type,
            "quantity": decimal_to_string(self.quantity),
        }

        if self.order_type == "LIMIT":
            if self.price is None:
                raise ValidationError("price is required for LIMIT orders.")
            params["timeInForce"] = self.time_in_force or "GTC"
            params["price"] = decimal_to_string(self.price)

        if self.order_type == "STOP_MARKET":
            if self.stop_price is None:
                raise ValidationError("stop_price is required for STOP_MARKET orders.")
            params["stopPrice"] = decimal_to_string(self.stop_price)

        return params


def build_order_request(
    *,
    symbol: str,
    side: str,
    order_type: str,
    quantity: str,
    price: str | None = None,
    stop_price: str | None = None,
) -> OrderRequest:
    normalized_symbol = (symbol or "").strip().upper()
    normalized_side = (side or "").strip().upper()
    normalized_order_type = (order_type or "").strip().upper()

    if not normalized_symbol:
        raise ValidationError("symbol is required.")
    if not SYMBOL_PATTERN.fullmatch(normalized_symbol):
        raise ValidationError("symbol must look like BTCUSDT.")
    if normalized_side not in VALID_SIDES:
        raise ValidationError("side must be BUY or SELL.")
    if normalized_order_type not in VALID_ORDER_TYPES:
        raise ValidationError("order type must be MARKET, LIMIT, or STOP_MARKET.")

    parsed_quantity = parse_positive_decimal(quantity, field_name="quantity")

    parsed_price: Decimal | None = None
    if normalized_order_type == "LIMIT":
        if price is None:
            raise ValidationError("price is required when order type is LIMIT.")
        parsed_price = parse_positive_decimal(price, field_name="price")
    elif price is not None:
        raise ValidationError("price can only be used with LIMIT orders.")

    parsed_stop_price: Decimal | None = None
    if normalized_order_type == "STOP_MARKET":
        if stop_price is None:
            raise ValidationError("stop_price is required when order type is STOP_MARKET.")
        parsed_stop_price = parse_positive_decimal(stop_price, field_name="stop_price")
    elif stop_price is not None:
        raise ValidationError("stop_price can only be used with STOP_MARKET orders.")

    return OrderRequest(
        symbol=normalized_symbol,
        side=normalized_side,
        order_type=normalized_order_type,
        quantity=parsed_quantity,
        price=parsed_price,
        stop_price=parsed_stop_price,
        time_in_force="GTC" if normalized_order_type == "LIMIT" else None,
    )


def validate_symbol_rules(order_request: OrderRequest, symbol_info: dict[str, Any] | None) -> None:
    if symbol_info is None:
        raise ValidationError(f"symbol {order_request.symbol} is not available on Binance Futures Testnet.")

    if order_request.order_type not in set(symbol_info.get("orderTypes", [])):
        raise ValidationError(
            f"{order_request.order_type} orders are not supported for {order_request.symbol}."
        )

    filters = {
        item["filterType"]: item
        for item in symbol_info.get("filters", [])
        if "filterType" in item
    }

    quantity_filter_name = (
        "MARKET_LOT_SIZE"
        if order_request.order_type == "MARKET" and "MARKET_LOT_SIZE" in filters
        else "LOT_SIZE"
    )
    quantity_filter = filters.get(quantity_filter_name)
    if quantity_filter:
        _validate_numeric_filter(
            order_request.quantity,
            minimum=quantity_filter.get("minQty"),
            maximum=quantity_filter.get("maxQty"),
            increment=quantity_filter.get("stepSize"),
            field_name="quantity",
        )

    if order_request.order_type == "LIMIT" and order_request.price is not None:
        price_filter = filters.get("PRICE_FILTER")
        if price_filter:
            _validate_numeric_filter(
                order_request.price,
                minimum=price_filter.get("minPrice"),
                maximum=price_filter.get("maxPrice"),
                increment=price_filter.get("tickSize"),
                field_name="price",
            )

    if order_request.order_type == "STOP_MARKET" and order_request.stop_price is not None:
        price_filter = filters.get("PRICE_FILTER")
        if price_filter:
            _validate_numeric_filter(
                order_request.stop_price,
                minimum=price_filter.get("minPrice"),
                maximum=price_filter.get("maxPrice"),
                increment=price_filter.get("tickSize"),
                field_name="stop_price",
            )


def parse_positive_decimal(value: str | Decimal, *, field_name: str) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ValidationError(f"{field_name} must be a valid number.") from exc

    if decimal_value <= 0:
        raise ValidationError(f"{field_name} must be greater than zero.")

    return decimal_value


def decimal_to_string(value: Decimal) -> str:
    string_value = format(value.normalize(), "f")
    if "." in string_value:
        string_value = string_value.rstrip("0").rstrip(".")
    return string_value or "0"


def _validate_numeric_filter(
    value: Decimal,
    *,
    minimum: str | None,
    maximum: str | None,
    increment: str | None,
    field_name: str,
) -> None:
    minimum_decimal = _safe_decimal(minimum)
    maximum_decimal = _safe_decimal(maximum)
    increment_decimal = _safe_decimal(increment)

    if minimum_decimal is not None and minimum_decimal > 0 and value < minimum_decimal:
        raise ValidationError(
            f"{field_name} must be at least {decimal_to_string(minimum_decimal)}."
        )

    if maximum_decimal is not None and maximum_decimal > 0 and value > maximum_decimal:
        raise ValidationError(
            f"{field_name} must be at most {decimal_to_string(maximum_decimal)}."
        )

    if increment_decimal is not None and increment_decimal > 0 and not _is_increment_aligned(
        value, increment_decimal
    ):
        raise ValidationError(
            f"{field_name} must align with step size {decimal_to_string(increment_decimal)}."
        )


def _is_increment_aligned(value: Decimal, increment: Decimal) -> bool:
    quotient = value / increment
    return quotient == quotient.to_integral_value()


def _safe_decimal(raw_value: str | None) -> Decimal | None:
    if raw_value in {None, ""}:
        return None
    try:
        return Decimal(raw_value)
    except InvalidOperation:
        return None
