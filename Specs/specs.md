System Overview
---------------
- Goal: Provide a TradingView-style web UI that can run Lean algorithms on-demand, visualize results (candles, indicators, trades, equity), and browse arbitrary market data.
- Tech Stack (planned):
  - Frontend: React (Vite) + lightweight-charts (or similar) for OHLC/indicator rendering.
  - Backend: Python FastAPI (candidate) orchestrating Lean CLI runs, data processing, and REST endpoints.
  - Lean artifacts: existing strategy `rsi_ma_cross.py`, `lean-config.json`, backtest outputs under `results/`.

Feature Requirements
--------------------
1. Algorithm Selection
	- Present list of available Lean algorithms with metadata (id, title, description, default params).
	- Allow user to launch backtests with chosen algorithm.

2. Parameter Controls
	- Inputs: symbol (text with autocomplete), timeframe (daily, minute, etc.), optional start/end dates.
	- Support algorithm-specific overrides (e.g., RSI period) via dynamic form.

3. Backtest Execution UX
	- User submits run → backend kicks off Lean CLI, returns job id.
	- UI shows queued/running/completed status with progress indicator.
	- When complete, load charts/trades/statistics into UI.

4. Charting & Visualization
	- Primary candle chart with price, overlay indicators, and entry/exit markers.
	- Secondary panes/tabs: equity curve, drawdown, RSI panel, trades table, metrics summary.
	- Timeframe controls synced across charts.

5. Market Data Explorer
	- Users can view price charts for any supported symbol/timeframe without running a backtest.
	- Backend serves OHLCV slices from Lean data directory (zip/CSV) or cached requests.

6. Indicator Support
	- Base indicators: RSI, SMA of RSI (existing), plus extension hooks for future overlays/oscillators.

Backend Responsibilities
------------------------
- Maintain algorithm manifest (JSON/YAML) describing each strategy and its parameters.
- Translate UI requests into Lean config overrides, launch `lean backtest`, capture output JSON.
- Normalize Lean result JSON to frontend-friendly schema (charts, orders, stats, parameters used).
- Provide REST endpoints:
  - `GET /algorithms`
  - `POST /backtests`
  - `GET /backtests/{id}` for status/results
  - `GET /market-data?symbol=...&timeframe=...` for candles

Data Sources
------------
- Lean data: `../Lean/Data/equity/usa/daily/spy.zip` (already exported sample to `results/spy_daily_2016_2020.json`).
- Backtest results: `results/RsiMaCrossAlgorithm*.json` (charts, orders, statistics).

Completed Work
--------------
- Export utility `scripts/export_spy_daily.py` generates SPY OHLCV JSON for rapid UI prototyping.
- React frontend in `ui/` delivers the algorithm picker, timeframe controls, tabbed views, and placeholder visualizations.
- Requirement documentation housed in `Specs/` keeps product scope aligned across teams.
- FastAPI backend (`backend/app.py`) now launches Lean via the CLI, tracks job lifecycle, and normalizes backtest outputs (equity, candles, trades, orders, indicators, statistics) for the UI.
- React UI consumes live Lean backtest payloads (candles, trades, orders) and renders them in-tab tables while polling job status.
- Automated smoke test (FastAPI `TestClient`) validates job lifecycle and market data endpoints.
- Local dev runbook validated: installed missing `uvicorn`/FastAPI dependencies, confirmed backend live on `http://127.0.0.1:8000`, and brought up the Vite UI server on `http://localhost:5173/`.
- Backend pytest suite (`backend/tests/test_app.py`) covers service endpoints plus the JSON normalization helpers (price series, orders, indicators, trades) to protect core logic.
- Added orchestration tests that mock Lean execution to exercise `_run_backtest_job` success/error paths without invoking Dotnet, ensuring job state transitions stay healthy.
- UI contract tests (`ui/src/api/client.test.js`) run with Vitest to assert REST client semantics and error handling against the backend payload schema.
- Cleaned up stale pip metadata (`~ip-25.2.dist-info`) so dependency installs no longer raise "invalid distribution" warnings.

Architecture Diagram
--------------------
```mermaid
flowchart LR
	user((User)) --> ui[React UI (Vite)]
	ui -->|REST calls| backend[FastAPI Backend]
	backend -->|manifest lookup| manifest[(Algorithm Manifest)]
	backend -->|spawn job| lean[Lean CLI Runner]
	lean --> results[(Backtest Results JSON)]
	backend -->|normalize charts & trades| results
	backend -->|read candles| data[(Lean Data Files)]
	backend -->|API responses| ui
	ui --> charts[[Charts & Tables]]
```

Outstanding Work
----------------
1. Surface additional analytics (drawdown series, benchmark comparison, order P&L) that the UI will eventually visualize.
2. Persist recent backtest runs and expose a job history view within the UI.
3. Expand automated coverage to include frontend component/unit tests (post-charting) and an end-to-end harness that drives the UI against the live FastAPI dev server.
4. Integrate a production-grade charting library (e.g., lightweight-charts) wired to backend candle/indicator feeds.
5. Document the validated backend/UI startup runbook and ensure future environment bootstrap pulls in FastAPI/Uvicorn out of the box.
6. Tackle npm audit issues (five moderate vulnerabilities flagged) or document acceptable risk/mitigations.
7. Perform manual end-to-end QA after each iteration (launch UI at `http://localhost:5173/`, trigger a Lean backtest, verify tables/charts) until automated coverage is in place.
