from __future__ import annotations

import argparse
import logging
import os
import sys
from decimal import Decimal, InvalidOperation

from bot.client import (
    DEFAULT_BASE_URL,
    BinanceAPIError,
    BinanceFuturesClient,
    ConfigurationError,
    NetworkError,
)
from bot.logging_config import configure_logging
from bot.orders import OrderService
from bot.validators import OrderRequest, ValidationError, build_order_request, decimal_to_string


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Place MARKET, LIMIT, or STOP_MARKET orders on Binance Futures Testnet (USDT-M).",
    )
    parser.add_argument("--symbol", required=True, help="Trading symbol, for example BTCUSDT.")
    parser.add_argument("--side", required=True, help="Order side: BUY or SELL.")
    parser.add_argument(
        "--type",
        dest="order_type",
        required=True,
        help="Order type: MARKET, LIMIT, or STOP_MARKET.",
    )
    parser.add_argument("--quantity", required=True, help="Order quantity, for example 0.001.")
    parser.add_argument(
        "--price",
        help="Limit price. Required when --type LIMIT is used.",
    )
    parser.add_argument(
        "--stop-price",
        dest="stop_price",
        help="Stop price. Required when --type STOP_MARKET is used.",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("BINANCE_BASE_URL", DEFAULT_BASE_URL),
        help=f"Binance base URL. Default: {DEFAULT_BASE_URL}",
    )
    parser.add_argument(
        "--recv-window",
        type=int,
        default=5000,
        help="Binance recvWindow in milliseconds. Default: 5000.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP timeout in seconds. Default: 10.",
    )
    return parser


def print_order_request_summary(order_request: OrderRequest) -> None:
    print("Order request summary")
    print(f"  Symbol: {order_request.symbol}")
    print(f"  Side: {order_request.side}")
    print(f"  Type: {order_request.order_type}")
    print(f"  Quantity: {decimal_to_string(order_request.quantity)}")
    if order_request.price is not None:
        print(f"  Price: {decimal_to_string(order_request.price)}")
        print(f"  Time in Force: {order_request.time_in_force}")
    if order_request.stop_price is not None:
        print(f"  Stop Price: {decimal_to_string(order_request.stop_price)}")
    print()


def print_order_response(response: dict[str, object]) -> None:
    avg_price = _extract_avg_price(response)

    print("Order response details")
    print(f"  orderId: {response.get('orderId', 'N/A')}")
    print(f"  status: {response.get('status', 'N/A')}")
    print(f"  executedQty: {response.get('executedQty', 'N/A')}")
    print(f"  avgPrice: {avg_price or 'N/A'}")
    print()


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    log_file = configure_logging()
    logger = logging.getLogger("trading_bot.cli")

    order_request: OrderRequest | None = None
    client: BinanceFuturesClient | None = None

    try:
        order_request = build_order_request(
            symbol=args.symbol,
            side=args.side,
            order_type=args.order_type,
            quantity=args.quantity,
            price=args.price,
            stop_price=args.stop_price,
        )
        print_order_request_summary(order_request)
        sys.stdout.flush()

        client = BinanceFuturesClient(
            api_key=os.getenv("BINANCE_API_KEY"),
            api_secret=os.getenv("BINANCE_API_SECRET"),
            base_url=args.base_url,
            timeout=args.timeout,
            recv_window=args.recv_window,
        )
        service = OrderService(client)
        result = service.place_order(order_request)

        print_order_response(result.response)
        print("SUCCESS: Order submitted to Binance Futures Testnet.")
        print(f"Log file: {log_file}")
        return 0

    except ValidationError as exc:
        logger.error("Invalid CLI input.", extra={"event": "validation_error", "error": str(exc)})
        print(f"FAILURE: {exc}", file=sys.stderr)
        print(f"Log file: {log_file}", file=sys.stderr)
        return 2

    except ConfigurationError as exc:
        logger.error("Missing Binance credentials.", extra={"event": "configuration_error", "error": str(exc)})
        print(f"FAILURE: {exc}", file=sys.stderr)
        print(f"Log file: {log_file}", file=sys.stderr)
        return 2

    except NetworkError as exc:
        logger.exception("Network failure while calling Binance.")
        print(f"FAILURE: Network error while contacting Binance: {exc}", file=sys.stderr)
        print(f"Log file: {log_file}", file=sys.stderr)
        return 1

    except BinanceAPIError as exc:
        logger.exception("Binance rejected the order.")
        print(f"FAILURE: {exc}", file=sys.stderr)
        print(f"Log file: {log_file}", file=sys.stderr)
        return 1

    finally:
        if client is not None:
            client.close()


def _extract_avg_price(response: dict[str, object]) -> str | None:
    raw_avg_price = response.get("avgPrice")
    if raw_avg_price not in {None, "", "0", "0.0", "0.00000"}:
        return str(raw_avg_price)

    cum_quote = response.get("cumQuote")
    executed_qty = response.get("executedQty")
    if cum_quote in {None, "", "0", "0.0"} or executed_qty in {None, "", "0", "0.0"}:
        return None

    try:
        calculated_avg_price = Decimal(str(cum_quote)) / Decimal(str(executed_qty))
    except (InvalidOperation, ZeroDivisionError):
        return None

    return decimal_to_string(calculated_avg_price)


if __name__ == "__main__":
    raise SystemExit(main())
