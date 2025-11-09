# Backend Service (FastAPI)

FastAPI application that orchestrates QuantConnect Lean backtests and normalizes results for the React UI.

## Responsibilities

- Serve the algorithm manifest (`GET /algorithms`).
- Launch Lean backtests (`POST /backtests`) and expose job status/results (`GET /backtests/{id}`).
- Provide prototype market data slices (`GET /market-data`).
- Translate Lean JSON output into UI-friendly structures (candles, equity, indicators, trades, orders, metrics).

## Setup & Run

```bash
# from repo root
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

cd backend
../.venv/bin/uvicorn app:app --reload
```

If port `8000` is already bound:

```bash
lsof -i tcp:8000
kill <pid>
```

## Key Files

- `app.py` – FastAPI app, Lean job orchestration, normalization helpers.
- `algorithms.json` – Strategy manifest with defaults and entry points.
- `tests/test_app.py` – Pytest coverage for endpoints and data shaping logic.
- `sample_backtest.json` – Legacy stub payload (kept for regression fixtures).

## Lean Integration Notes

- Backtests write under `../storage/backtests/<job-id>/` using generated `lean-config.json` files.
- Ensure required data (e.g., minute QQQ) exists in `../Lean/Data` before requesting corresponding timeframes.
- Override `PYTHONNET_PYDLL` if Lean cannot locate a Python runtime.

## Update Checklist

- Sync `algorithms.json` whenever new strategies or defaults are introduced.
- Extend `_extract_*` helpers in `app.py` when Lean payload formats evolve.
- Back test changes with `pytest` to protect normalization logic.
