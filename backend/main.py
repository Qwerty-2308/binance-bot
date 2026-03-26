"""
Binance-Powered Portfolio Tracker — FastAPI Backend
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional

from binance.client import Client as BinanceClient
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()

# ── Config ─────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

BINANCE_API_KEY    = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
DATABASE_URL       = os.getenv("DATABASE_URL", "sqlite:///./tracker.db")

# ── Database ────────────────────────────────────────────────────────────────
connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
engine       = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"
    username        = Column(String, primary_key=True, index=True)
    hashed_password = Column(String, nullable=False)


Base.metadata.create_all(bind=engine)

# ── Security ────────────────────────────────────────────────────────────────
pwd_ctx       = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_binance() -> BinanceClient:
    return BinanceClient(BINANCE_API_KEY, BINANCE_API_SECRET, testnet=True)


# ── Schemas ──────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TradeRequest(BaseModel):
    symbol:   str
    side:     str      # BUY | SELL
    quantity: float

class TradeResponse(BaseModel):
    order_id:     int
    symbol:       str
    side:         str
    status:       str
    executed_qty: str
    avg_price:    str

class PriceResponse(BaseModel):
    symbol: str
    price:  str

class BalanceItem(BaseModel):
    asset:  str
    free:   str
    locked: str

class OrderModel(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String, index=True, nullable=False)
    symbol = Column(String, nullable=False)
    side = Column(String, nullable=False)
    quantity = Column(String, nullable=False)
    executed_qty = Column(String, nullable=False)
    avg_price = Column(String, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(String, nullable=False)


class OrderResponse(BaseModel):
    id: str
    username: str
    symbol: str
    side: str
    quantity: str
    executed_qty: str
    avg_price: str
    status: str
    created_at: str


# ── Auth helpers ─────────────────────────────────────────────────────────────
def hash_password(pw: str) -> str:
    return pwd_ctx.hash(pw)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)

def create_access_token(subject: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": subject, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> UserModel:
    token = credentials.credentials
    try:
        payload  = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if not username:
            raise ValueError
    except (JWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(UserModel).filter(UserModel.username == username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Portfolio Tracker API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def seed_demo_user():
    """Create a demo/demo123 account so the app works out of the box."""
    db = SessionLocal()
    if not db.query(UserModel).filter(UserModel.username == "demo").first():
        db.add(UserModel(username="demo", hashed_password=hash_password("demo123")))
        db.commit()
    db.close()


# ── Auth ──────────────────────────────────────────────────────────────────────
@app.post("/auth/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(UserModel).filter(UserModel.username == body.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")
    db.add(UserModel(username=body.username, hashed_password=hash_password(body.password)))
    db.commit()
    return TokenResponse(access_token=create_access_token(body.username))


@app.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.username == body.username).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(access_token=create_access_token(user.username))


# ── Market ────────────────────────────────────────────────────────────────────
@app.get("/market/price/{symbol}", response_model=PriceResponse)
def get_price(symbol: str, _: UserModel = Depends(get_current_user)):
    try:
        ticker = get_binance().futures_symbol_ticker(symbol=symbol.upper())
        return PriceResponse(symbol=ticker["symbol"], price=ticker["price"])
    except BinanceAPIException as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/market/prices", response_model=list[PriceResponse])
def get_prices(symbols: str = "BTCUSDT,ETHUSDT", _: UserModel = Depends(get_current_user)):
    client, result = get_binance(), []
    for sym in symbols.upper().split(","):
        try:
            t = client.futures_symbol_ticker(symbol=sym.strip())
            result.append(PriceResponse(symbol=t["symbol"], price=t["price"]))
        except BinanceAPIException:
            pass
    return result


# ── Trade ─────────────────────────────────────────────────────────────────────
@app.post("/trade", response_model=TradeResponse)
def place_trade(body: TradeRequest, _: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.side.upper() not in {"BUY", "SELL"}:
        raise HTTPException(status_code=422, detail="side must be BUY or SELL")
    if body.quantity <= 0:
        raise HTTPException(status_code=422, detail="quantity must be positive")
    try:
        order = get_binance().futures_create_order(
            symbol=body.symbol.upper(), side=body.side.upper(),
            type="MARKET", quantity=body.quantity,
        )
        order_record = OrderModel(
            username=_.username,
            symbol=order["symbol"],
            side=order["side"],
            quantity=str(body.quantity),
            executed_qty=order.get("executedQty", "0"),
            avg_price=order.get("avgPrice", "0"),
            status=order["status"],
            created_at=datetime.utcnow().isoformat(),
        )
        db.add(order_record)
        db.commit()
        db.refresh(order_record)

        return TradeResponse(
            order_id=order_record.id,      symbol=order_record.symbol,
            side=order_record.side,        status=order_record.status,
            executed_qty=order_record.executed_qty,
            avg_price=order_record.avg_price,
        )
    except BinanceAPIException as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/orders", response_model=list[OrderResponse])
def get_orders(_: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    orders = db.query(OrderModel).filter(OrderModel.username == _.username).order_by(OrderModel.id.desc()).all()
    return [
        OrderResponse(
            id=o.id,
            username=o.username,
            symbol=o.symbol,
            side=o.side,
            quantity=o.quantity,
            executed_qty=o.executed_qty,
            avg_price=o.avg_price,
            status=o.status,
            created_at=o.created_at,
        )
        for o in orders
    ]


# ── Account ───────────────────────────────────────────────────────────────────
@app.get("/account/balance", response_model=list[BalanceItem])
def get_balance(_: UserModel = Depends(get_current_user)):
    try:
        account = get_binance().futures_account()
        return [
            BalanceItem(asset=a["asset"], free=a["availableBalance"], locked="0")
            for a in account.get("assets", [])
            if float(a.get("walletBalance", 0)) > 0
        ]
    except BinanceAPIException as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
