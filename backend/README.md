# Backend Service (FastAPI)

Prototype API that exposes QuantConnect Lean algorithms, runs backtests, and serves market data to the React UI.

## Commands

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```

## REST Endpoints

- `GET /` – Health check.
- `GET /algorithms` – Manifest of available algorithms with default parameters.
- `POST /backtests` – Launch a backtest (currently returns sample result immediately).
- `GET /backtests/{jobId}` – Retrieve backtest status/results.
- `GET /market-data?symbol=SPY&timeframe=1D` – Sample OHLCV candles for prototype UI.

`POST /backtests`/`GET /backtests/{jobId}` currently hydrate responses from `sample_backtest.json`. Replace the stubs once Lean orchestration is wired up.
