# Binance-Powered Portfolio Tracker

Full-stack app — FastAPI backend + React (Vite) frontend — connected to the **Binance Futures Testnet**.

## Stack
| Layer    | Tech |
|----------|------|
| Backend  | FastAPI, python-binance, SQLAlchemy (SQLite), python-jose (JWT), passlib (bcrypt) |
| Frontend | React 18, Vite, Axios |

## Project Structure
```
portfolio_tracker/
├── backend/
│   ├── main.py           # All FastAPI routes, models, auth, Binance calls
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── App.jsx        # Login page + Dashboard (prices, trade, balances)
    │   └── api.js         # Axios instance + JWT interceptor + all API calls
    ├── package.json
    └── vite.config.js
```

## Setup (≈ 10 minutes)

### 1. Binance Testnet Credentials
1. Visit https://testnet.binancefuture.com
2. Log in → API Management → generate a key pair

### 2. Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your keys
uvicorn main:app --reload --port 8000
```
Docs at http://localhost:8000/docs  
Auto-created demo account: **demo / demo123**

### 3. Frontend
```bash
cd frontend
npm install && npm run dev
```
App at http://localhost:5173

## API Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/login` | — | Returns JWT |
| POST | `/auth/register` | — | Create account |
| GET | `/market/price/{symbol}` | JWT | Single live price |
| GET | `/market/prices?symbols=X,Y` | JWT | Multiple prices |
| POST | `/trade` | JWT | Market order |
| GET | `/account/balance` | JWT | Testnet balances |

## .env Reference
```
BINANCE_API_KEY=your_testnet_key
BINANCE_API_SECRET=your_testnet_secret
JWT_SECRET_KEY=super-secret-change-me
DATABASE_URL=sqlite:///./tracker.db
```

## Notes
- Testnet only — remove `testnet=True` in `main.py` for production
- JWT expiry: 60 min (adjust `ACCESS_TOKEN_EXPIRE_MINUTES`)
- All trades are MARKET orders; extend `TradeRequest` for LIMIT support
