from __future__ import annotations

import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from bot.client import (
    DEFAULT_BASE_URL,
    BinanceAPIError,
    BinanceFuturesClient,
    ConfigurationError,
    NetworkError,
)
from bot.logging_config import configure_logging
from bot.orders import OrderService
from bot.validators import ValidationError, build_order_request


LOG_FILE = configure_logging()
logger = logging.getLogger("trading_bot.api")

app = FastAPI(title="Binance Futures Testnet Trading Bot API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_SESSION_CREDENTIALS: dict[str, str] = {}


class OrderPayload(BaseModel):
    symbol: str = Field(..., examples=["BTCUSDT"])
    side: str = Field(..., examples=["BUY"])
    order_type: str = Field(..., examples=["MARKET"])
    quantity: str = Field(..., examples=["0.001"])
    price: str | None = Field(default=None, examples=["80000"])
    stop_price: str | None = Field(default=None, examples=["78000"])

class CredentialsPayload(BaseModel):
    api_key: str = Field(..., min_length=5, examples=["your_testnet_api_key"])
    api_secret: str = Field(..., min_length=5, examples=["your_testnet_api_secret"])


@app.get("/api/health")
def health() -> dict[str, object]:
    env_configured = bool(os.getenv("BINANCE_API_KEY") and os.getenv("BINANCE_API_SECRET"))
    session_configured = bool(
        _SESSION_CREDENTIALS.get("api_key") and _SESSION_CREDENTIALS.get("api_secret")
    )
    credentials_configured = env_configured or session_configured

    if env_configured:
        source = "env"
    elif session_configured:
        source = "session"
    else:
        source = "missing"
    return {
        "status": "ok",
        "credentialsConfigured": credentials_configured,
        "credentialsSource": source,
        "baseUrl": os.getenv("BINANCE_BASE_URL", DEFAULT_BASE_URL),
        "logFile": str(LOG_FILE),
    }

@app.post("/api/session/credentials")
def set_session_credentials(payload: CredentialsPayload) -> dict[str, object]:
    _SESSION_CREDENTIALS["api_key"] = payload.api_key.strip()
    _SESSION_CREDENTIALS["api_secret"] = payload.api_secret.strip()
    logger.info("Stored Binance credentials in session memory.", extra={"event": "session_credentials_set"})
    return {"success": True}


@app.delete("/api/session/credentials")
def clear_session_credentials() -> dict[str, object]:
    _SESSION_CREDENTIALS.clear()
    logger.info("Cleared Binance session credentials.", extra={"event": "session_credentials_cleared"})
    return {"success": True}


@app.post("/api/orders")
def place_order(payload: OrderPayload) -> dict[str, object]:
    logger.info(
        "Received order placement request from web UI.",
        extra={
            "event": "web_order_request",
            "symbol": payload.symbol,
            "side": payload.side,
            "order_type": payload.order_type,
        },
    )

    client: BinanceFuturesClient | None = None
    try:
        order_request = build_order_request(
            symbol=payload.symbol,
            side=payload.side,
            order_type=payload.order_type,
            quantity=payload.quantity,
            price=payload.price,
            stop_price=payload.stop_price,
        )

        api_key = os.getenv("BINANCE_API_KEY") or _SESSION_CREDENTIALS.get("api_key")
        api_secret = os.getenv("BINANCE_API_SECRET") or _SESSION_CREDENTIALS.get("api_secret")

        client = BinanceFuturesClient(
            api_key=api_key,
            api_secret=api_secret,
            base_url=os.getenv("BINANCE_BASE_URL", DEFAULT_BASE_URL),
        )
        service = OrderService(client)
        result = service.place_order(order_request)

        return {
            "success": True,
            "message": "Order submitted to Binance Futures Testnet.",
            "request": result.request_params,
            "response": result.response,
            "logFile": str(LOG_FILE),
        }

    except ValidationError as exc:
        logger.error(
            "Validation failed for web order request.",
            extra={"event": "validation_error", "error": str(exc)},
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    except ConfigurationError as exc:
        logger.error(
            "Missing Binance credentials for web order request.",
            extra={"event": "configuration_error", "error": str(exc)},
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    except NetworkError as exc:
        logger.exception("Network error while placing order from web UI.")
        raise HTTPException(
            status_code=502,
            detail=f"Network error while contacting Binance: {exc}",
        ) from exc

    except BinanceAPIError as exc:
        logger.exception("Binance rejected the web order request.")
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    finally:
        if client is not None:
            client.close()
