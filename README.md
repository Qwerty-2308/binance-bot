# Binance Futures Testnet Trading Bot

Small Python trading bot for Binance Futures Testnet (USDT-M) with:

- a reusable Python service layer
- a CLI for direct order placement
- a React frontend backed by a Python API
- structured logging and clear error handling

## Project structure

```text
.
├── app.py
├── bot
│   ├── __init__.py
│   ├── client.py
│   ├── logging_config.py
│   ├── orders.py
│   └── validators.py
├── cli.py
├── frontend
│   ├── index.html
│   ├── package.json
│   ├── src
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── styles.css
│   └── vite.config.js
├── logs
├── README.md
└── requirements.txt
```

## Features

- Places `MARKET`, `LIMIT`, and `STOP_MARKET` orders on Binance Futures Testnet
- Supports both `BUY` and `SELL`
- Validates CLI input before calling Binance
- Validates the symbol, quantity step size, and price / stop price tick size against Binance exchange filters
- Logs API requests, responses, and errors to a timestamped file under `logs/`
- Handles invalid input, API failures, and network failures with clear terminal output
- Exposes a small web API and a React UI for browser-based order placement

## Backend setup

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Export your Binance Futures Testnet credentials:

```bash
export BINANCE_API_KEY="your_testnet_api_key"
export BINANCE_API_SECRET="your_testnet_api_secret"
export BINANCE_BASE_URL="https://testnet.binancefuture.com"
```

## Run the CLI

### MARKET order example

```bash
python3 cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
```

### LIMIT order example

```bash
python3 cli.py --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 80000
```

### STOP_MARKET order example (bonus)

```bash
python3 cli.py --symbol BTCUSDT --side SELL --type STOP_MARKET --quantity 0.001 --stop-price 78000
```

## Run the web app

### 1. Start the Python API

```bash
uvicorn app:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

### 2. Start the React frontend

```bash
cd frontend
npm install
npm run dev
```

The React app will be available at `http://127.0.0.1:5173`.

## CLI arguments

- `--symbol`: required, for example `BTCUSDT`
- `--side`: required, `BUY` or `SELL`
- `--type`: required, `MARKET`, `LIMIT`, or `STOP_MARKET`
- `--quantity`: required, positive decimal quantity
- `--price`: required only for `LIMIT`
- `--stop-price`: required only for `STOP_MARKET`
- `--base-url`: optional, defaults to `https://testnet.binancefuture.com`
- `--recv-window`: optional, defaults to `5000`
- `--timeout`: optional, defaults to `10`

## Output

Each run prints:

- order request summary
- order response details
- success or failure message
- generated log file path

The web UI shows:

- backend health and credential status
- a validated order form
- request and response summaries
- success and failure states
- the active log file path

## Logging

Every CLI execution creates a new log file inside `logs/`, for example:

```text
logs/trading_bot_20260325_153012.log
```

The log file contains JSON-formatted entries for:

- outgoing API requests
- incoming API responses
- validation failures
- API errors
- network errors

To satisfy the assignment deliverable, run at least:

1. one `MARKET` order
2. one `LIMIT` order

That will produce separate log files you can submit with the repository.

## Assumptions

- This project targets the Binance Futures Testnet USDT-M API base URL: `https://testnet.binancefuture.com`
- Credentials are supplied through environment variables rather than CLI flags
- The account is used in one-way mode, so `positionSide` is not required
- `LIMIT` orders use `GTC` by default
- The app does not auto-round invalid price or quantity values; it fails fast with a validation message instead
- The React frontend talks to the Python API on `http://127.0.0.1:8000`

## Notes

- If Binance rejects an order for margin, leverage, or account-specific reasons, the API error is surfaced directly in the CLI and written to the log file
- Actual market/limit log files require valid testnet credentials and live API calls, so generate them after exporting your own keys
