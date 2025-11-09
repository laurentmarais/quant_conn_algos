# QuantConnect Control Room UI

Vite + React frontend that manages algorithm selection, parameter editing, and visualization of Lean backtest output.

## Commands

```bash
cd ui
npm install        # first run
npm run dev        # start dev server
npm run build      # production build
npm run test -- --run   # vitest suite
```

The dev server defaults to `http://localhost:5173/`. If the port is occupied, Vite increments (e.g., `5174`, `5175`).

## Key Components

- `src/App.jsx` – Application shell, algorithm picker, parameter state, backtest polling, and tab layout.
- `src/components/ParameterControls.jsx` – Sidebar editor for algorithm-specific parameters with reset helpers.
- `src/components/PriceChart.jsx` – Candle chart with trade markers using `lightweight-charts`.
- `src/components/TimeSeriesChart.jsx` – Shared line/area chart for equity and indicator series.
- `src/api/client.js` – REST client helpers for backend endpoints.
- `src/mock/data.js` – Mock manifest/backtest payloads for offline development.

## Testing

- `npm run test -- --run` executes vitest unit/contract tests.
- Add component tests beside new modules under `src/`.

## Update Checklist

- Keep `src/api/client.js` in sync with backend payloads.
- Update `src/mock/data.js` when backend schema changes.
- Add styles to `src/App.css` alongside new components.
