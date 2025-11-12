Project Orientation
-------------------
- **Working cadence**: Update documentation (this file, backend/README.md, ui/README.md) with every iteration before closing a task.
- **Snapshot checklist**: Confirm algorithms manifest matches Lean scripts, UI parameter controls align with manifest defaults, and startup instructions reflect latest runbook.
- **Documentation index**:
	- `Specs/specs.md` (this file) – product scope, architecture, outstanding work.
	- `backend/README.md` – API responsibilities, runbook, Lean integration notes.
	- `ui/README.md` – Frontend commands, key components, testing guidance.
	- `Specs/` directory is the source of truth for cross-team requirements; extend with sub-docs as features mature.

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

Key Modules Overview
--------------------
- `backend/app.py`: FastAPI service, Lean orchestration, parameter merging, and JSON normalization helpers.
- `backend/algorithms.json`: Manifest of available Lean strategies, default symbols/timeframes, and parameter seeds.
- `rsi_ma_cross.py` / `trend_follow_ema.py` / `bollinger_reversion.py`: Parameterized Lean algorithms sourcing inputs via `GetParameter`.
- `ui/src/App.jsx`: React shell coordinating algorithm selection, parameter state, run lifecycle, and chart/tab layout.
- `ui/src/components/PriceChart.jsx` & `TimeSeriesChart.jsx`: Lightweight-charts wrappers for candles, equity, and indicator series.
- `ui/src/components/ParameterControls.jsx`: Sidebar form rendering algorithm-specific parameter inputs with reset helpers.
- `ui/src/api/client.js`: REST client abstraction with fetch helpers and error normalization.

Completed Work
--------------
- Export utility `scripts/export_spy_daily.py` generates SPY OHLCV JSON for rapid UI prototyping.
- Requirement documentation housed in `Specs/` keeps product scope aligned across teams.
- FastAPI backend (`backend/app.py`) launches Lean via the CLI, merges user overrides with algorithm defaults, and normalizes backtest outputs (candles, trades, indicators, statistics) for the UI.
- Algorithm manifest expanded with multiple parameterized strategies (`rsi_ma_cross.py`, `trend_follow_ema.py`, `bollinger_reversion.py`) now callable from the UI.
- React frontend in `ui/` renders algorithm picker, timeframe controls, and lightweight-charts based visualizations (candles with trade markers, equity curve, indicator panes) using `PriceChart` and `TimeSeriesChart` components.
- React UI consumes live Lean backtest payloads (candles, trades, orders, indicators) and renders them in-tab charts/tables while polling job status.
- Automated smoke test (FastAPI `TestClient`) validates job lifecycle and market data endpoints.
- Backend pytest suite (`backend/tests/test_app.py`) covers service endpoints plus the JSON normalization helpers (price series, orders, indicators, trades) to protect core logic.
- Added orchestration tests that mock Lean execution to exercise `_run_backtest_job` success/error paths without invoking Dotnet, ensuring job state transitions stay healthy.
- UI contract tests (`ui/src/api/client.test.js`) run with Vitest to assert REST client semantics and error handling against the backend payload schema.
- Local dev runbook validated: installed missing `uvicorn`/FastAPI dependencies, confirmed backend live on `http://127.0.0.1:8000`, and brought up the Vite UI server on `http://localhost:5173/`.
- Cleaned up stale pip metadata (`~ip-25.2.dist-info`) so dependency installs no longer raise "invalid distribution" warnings.
- Sidebar parameter controls now mirror algorithm defaults and allow tweaking strategy inputs before launching a backtest, including reset-to-default helpers.
- Hardened trade normalization: `_extract_trades` now falls back to Lean report payloads, filters by symbol, and keeps order extraction intact so UI markers populate; regression test added and real backtest artifacts confirm 67 trades plus 731 daily candles for `SPY` between 2018-01-01 and 2019-12-31.

Local Run Instructions
----------------------
- Backend
	1. `cd backend`
	2. `../.venv/bin/uvicorn app:app --reload`
	3. If port 8000 is busy, stop the existing process (`lsof -i tcp:8000` then `kill <pid>`).
	4. Backend serves `http://127.0.0.1:8000` once the log prints “Application startup complete.”
- Frontend
	1. `cd ui`
	2. `npm install` (first run only)
	3. `npm run dev`
	4. Vite defaults to `http://localhost:5173`, but if that port is taken it will increment (e.g., `5174`, `5175`). Use the address shown in the terminal output or free the port with `lsof -i tcp:5173` / `kill <pid>`.

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
3. Expand automated coverage to include lightweight-charts component/unit tests plus an end-to-end harness that drives the UI against the live FastAPI dev server.
4. Harden the new parameter editor with type-aware validation, helper text, and guardrails (min/max bounds, safe ranges) per algorithm.
5. Document any deviations when additional backend dependencies are introduced so the startup runbook stays accurate.
6. Tackle npm audit issues (five moderate vulnerabilities flagged) or document acceptable risk/mitigations.
7. Perform manual end-to-end QA after each iteration (launch UI at `http://localhost:5173/`, trigger a Lean backtest, verify candles plus trade markers with the new extractor) until automated coverage is in place.
