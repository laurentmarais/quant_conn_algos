from __future__ import annotations

import datetime as dt
import copy
import json
import os
import shutil
import subprocess
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent

ALGORITHMS_PATH = ROOT / "algorithms.json"
SPY_SAMPLE_DATA_PATH = PROJECT_ROOT / "results/spy_daily_2016_2020.json"

LEAN_CONFIG_TEMPLATE_PATH = PROJECT_ROOT / "lean-config.json"
BACKTEST_STORAGE_ROOT = PROJECT_ROOT / "storage/backtests"
DEFAULT_PYTHONNET_PYDLL = Path(
    "/opt/homebrew/opt/python@3.11/Frameworks/Python.framework/Versions/3.11/lib/libpython3.11.dylib"
)

LEAN_LAUNCHER_PATH = Path(
    os.environ.get("LEAN_LAUNCHER_PATH", PROJECT_ROOT.parent / "Lean/Launcher")
)


ORDER_STATUS_LOOKUP = {
    0: "New",
    1: "Submitted",
    2: "PartiallyFilled",
    3: "Filled",
    4: "Canceled",
    5: "Canceled",
    6: "Canceled",
    7: "Invalid",
    8: "None",
}

ORDER_DIRECTION_LOOKUP = {0: "Buy", 1: "Sell"}

ORDER_TYPE_LOOKUP = {
    0: "Market",
    1: "Limit",
    2: "StopMarket",
    3: "StopLimit",
    4: "MarketOnOpen",
    5: "MarketOnClose",
    6: "LimitIfTouched",
    7: "OptionExercise",
    8: "OptionAssignment",
    9: "OptionExercise",
    10: "TrailingStop",
    11: "TrailingStopLimit",
    12: "ComboMarket",
    13: "ComboLimit",
    14: "ComboOneCancelsOther",
}


def _map_order_type(value: Any) -> str:
    try:
        return ORDER_TYPE_LOOKUP.get(int(value), str(value))
    except (TypeError, ValueError):
        return str(value)


def _map_order_status(value: Any) -> str:
    try:
        return ORDER_STATUS_LOOKUP.get(int(value), str(value))
    except (TypeError, ValueError):
        return str(value)


def _map_order_direction(value: Any) -> str:
    try:
        return ORDER_DIRECTION_LOOKUP.get(int(value), str(value))
    except (TypeError, ValueError):
        return str(value)


def _load_base_config() -> dict[str, Any]:
    try:
        return json.loads(LEAN_CONFIG_TEMPLATE_PATH.read_text())
    except FileNotFoundError as exc:  # pragma: no cover - configuration must exist
        raise RuntimeError("Missing lean-config.json template") from exc


BASE_LEAN_CONFIG: dict[str, Any] = _load_base_config()


def _ensure_storage_root() -> None:
    BACKTEST_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)


def _resolve_python_dll() -> str:
    overridden = os.environ.get("PYTHONNET_PYDLL")
    if overridden:
        return overridden
    if DEFAULT_PYTHONNET_PYDLL.exists():
        return str(DEFAULT_PYTHONNET_PYDLL)
    raise RuntimeError("Unable to locate a Python runtime for Lean (set PYTHONNET_PYDLL)")


def _resolve_algorithm_config(algorithm_id: str) -> dict[str, Any]:
    for algo in ALGORITHMS:
        if algo.get("id") == algorithm_id:
            return algo
    raise HTTPException(status_code=400, detail="Unknown algorithm id")


def _prepare_job_environment(job_id: str, payload: BacktestRequest) -> dict[str, Any]:
    _ensure_storage_root()
    job_dir = BACKTEST_STORAGE_ROOT / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)

    config = copy.deepcopy(BASE_LEAN_CONFIG)
    config["results-destination-folder"] = str(job_dir)

    algorithm_manifest = _resolve_algorithm_config(payload.algorithmId)
    entry_point = algorithm_manifest.get("entryPoint")
    if entry_point:
        config["algorithm-location"] = str((PROJECT_ROOT / entry_point).resolve())

    # Optional overrides for dates and parameters
    if payload.startDate:
        config["start-date"] = payload.startDate
    if payload.endDate:
        config["end-date"] = payload.endDate

    if payload.parameters:
        config["parameters"] = {
            key: str(value)
            for key, value in payload.parameters.items()
        }

    config_path = job_dir / "lean-config.json"
    config_path.write_text(json.dumps(config, indent=2))

    return {
        "job_dir": job_dir,
        "config_path": config_path,
        "algorithm_manifest": algorithm_manifest,
    }


def _parse_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        cleaned = cleaned.replace("$", "").replace(",", "")
        if cleaned.endswith("%"):
            cleaned = cleaned[:-1]
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return None
    return None


def _decimal_to_float(value: Optional[Decimal]) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def _parse_percentage(value: Any) -> Optional[float]:
    decimal_value = _parse_decimal(value)
    if decimal_value is None:
        return None
    return float(decimal_value / Decimal(100))


def _format_epoch_seconds(epoch: Any) -> str:
    try:
        seconds = int(epoch)
    except (TypeError, ValueError):
        return str(epoch)
    return dt.datetime.utcfromtimestamp(seconds).date().isoformat()


def _format_iso_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return value


def _extract_equity_curve(summary: dict[str, Any]) -> list[dict[str, Any]]:
    equity_values = (
        summary.get("charts", {})
        .get("Strategy Equity", {})
        .get("series", {})
        .get("Equity", {})
        .get("values", [])
    )
    curve: list[dict[str, Any]] = []
    for point in equity_values:
        if not isinstance(point, list) or len(point) < 2:
            continue
        time_label = _format_epoch_seconds(point[0])
        value = point[-1]
        decimal_value = _parse_decimal(value)
        if decimal_value is None:
            continue
        curve.append({"time": time_label, "value": float(decimal_value)})
    return curve


def _extract_price_series(report: dict[str, Any], symbol: str) -> list[dict[str, Any]]:
    charts = report.get("charts", {}) if report else {}
    candidate_chart = charts.get(symbol) or charts.get(symbol.upper())
    if not candidate_chart:
        candidate_chart = charts.get("Benchmark")
    if not candidate_chart:
        return []

    for series in candidate_chart.get("series", {}).values():
        values = series.get("values", [])
        if not values:
            continue

        price_points: list[dict[str, Any]] = []
        for point in values:
            if not isinstance(point, list) or len(point) < 2:
                continue

            timestamp = point[0]
            open_raw = point[1] if len(point) > 1 else None
            high_raw = point[2] if len(point) > 2 else open_raw
            low_raw = point[3] if len(point) > 3 else open_raw
            close_raw = point[4] if len(point) > 4 else point[-1]

            close_decimal = _parse_decimal(close_raw)
            if close_decimal is None:
                continue

            open_decimal = _parse_decimal(open_raw) or close_decimal
            high_decimal = _parse_decimal(high_raw) or close_decimal
            low_decimal = _parse_decimal(low_raw) or close_decimal

            price_points.append(
                {
                    "time": _format_epoch_seconds(timestamp),
                    "open": float(open_decimal),
                    "high": float(high_decimal),
                    "low": float(low_decimal),
                    "close": float(close_decimal),
                }
            )

        if price_points:
            return price_points

    return []


def _extract_indicator_series(chart: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    series = chart.get("series", {}) if chart else {}
    output: dict[str, list[dict[str, Any]]] = {"rsi": [], "rsiSma": []}

    rsi_series = series.get("RSI")
    if rsi_series:
        for point in rsi_series.get("values", []):
            if not isinstance(point, list) or len(point) < 2:
                continue
            time_label = _format_epoch_seconds(point[0])
            decimal_value = _parse_decimal(point[1])
            if decimal_value is not None:
                output["rsi"].append({"time": time_label, "value": float(decimal_value)})

    rsi_ma_series = series.get("RSI_MA")
    if rsi_ma_series:
        for point in rsi_ma_series.get("values", []):
            if not isinstance(point, list) or len(point) < 2:
                continue
            time_label = _format_epoch_seconds(point[0])
            decimal_value = _parse_decimal(point[1])
            if decimal_value is not None:
                output["rsiSma"].append({"time": time_label, "value": float(decimal_value)})

    return output


def _extract_trades(summary: dict[str, Any]) -> list[dict[str, Any]]:
    closed_trades = (
        summary.get("totalPerformance", {}).get("closedTrades")
        or []
    )
    trades: list[dict[str, Any]] = []
    for idx, trade in enumerate(closed_trades, start=1):
        entry_date = _format_iso_date(trade.get("entryTime"))
        exit_date = _format_iso_date(trade.get("exitTime"))
        entry_price = _parse_decimal(trade.get("entryPrice"))
        exit_price = _parse_decimal(trade.get("exitPrice"))
        profit = _parse_decimal(trade.get("profitLoss"))

        trades.append(
            {
                "id": idx,
                "direction": "Long" if trade.get("direction") == 0 else "Short",
                "entryTime": entry_date or str(trade.get("entryTime")),
                "exitTime": exit_date or str(trade.get("exitTime")),
                "entryPrice": float(entry_price) if entry_price is not None else 0.0,
                "exitPrice": float(exit_price) if exit_price is not None else 0.0,
                "quantity": trade.get("quantity", 0),
                "profit": float(profit) if profit is not None else 0.0,
            }
        )
    return trades


def _extract_orders(report: dict[str, Any]) -> list[dict[str, Any]]:
    order_map = (report or {}).get("orders", {})
    if not isinstance(order_map, dict):
        return []

    orders: list[dict[str, Any]] = []
    for order_id, order in order_map.items():
        if not isinstance(order, dict):
            continue

        price_decimal = _parse_decimal(order.get("price"))

        orders.append(
            {
                "id": int(order.get("id", order_id)),
                "symbol": order.get("symbol", {}).get("value"),
                "time": _format_iso_date(order.get("time")) or order.get("time"),
                "type": _map_order_type(order.get("type")),
                "direction": _map_order_direction(order.get("direction")),
                "status": _map_order_status(order.get("status")),
                "quantity": order.get("quantity"),
                "price": float(price_decimal) if price_decimal is not None else None,
                "lastFillTime": _format_iso_date(order.get("lastFillTime")) or order.get("lastFillTime"),
                "tag": order.get("tag") or "",
            }
        )

    orders.sort(key=lambda item: (item["time"] or "", item["id"]))
    return orders


def _build_backtest_result(
    job_id: str,
    payload: BacktestRequest,
    summary_path: Path,
    report_path: Path | None,
    job_env: dict[str, Any],
    lean_stdout: str,
    lean_stderr: str,
    duration_seconds: float,
) -> dict[str, Any]:
    base_job = JOB_STORE.get(job_id, {})
    summary = _load_json(summary_path)
    report = _load_json(report_path) if report_path and report_path.exists() else {}

    trade_stats = summary.get("totalPerformance", {}).get("tradeStatistics", {})
    portfolio_stats = summary.get("totalPerformance", {}).get("portfolioStatistics", {})
    statistics = summary.get("statistics", {})

    start_equity = _parse_decimal(portfolio_stats.get("startEquity"))
    net_profit_dollars = _parse_decimal(trade_stats.get("totalProfitLoss"))
    net_profit_percent = _parse_percentage(statistics.get("Net Profit"))

    metrics = {
        "totalTrades": trade_stats.get("totalNumberOfTrades"),
        "winningTrades": trade_stats.get("numberOfWinningTrades"),
        "losingTrades": trade_stats.get("numberOfLosingTrades"),
        "winRate": _parse_percentage(statistics.get("Win Rate")),
        "maxDrawdown": _parse_percentage(statistics.get("Drawdown")),
        "sharpe": _decimal_to_float(_parse_decimal(statistics.get("Sharpe Ratio"))),
        "sortino": _decimal_to_float(_parse_decimal(statistics.get("Sortino Ratio"))),
    }

    rsi_chart = report.get("charts", {}).get("RSI", {})
    indicators = _extract_indicator_series(rsi_chart)

    artifacts = {
        "summaryPath": str(summary_path),
        "reportPath": str(report_path) if report_path else None,
        "jobDirectory": str(job_env["job_dir"]),
        "stdout": lean_stdout.strip() or None,
        "stderr": lean_stderr.strip() or None,
    }

    order_events_path = next(job_env["job_dir"].glob("*-order-events.json"), None)
    if order_events_path:
        artifacts["orderEventsPath"] = str(order_events_path)

    log_path = next(job_env["job_dir"].glob("*.log"), None)
    if log_path:
        artifacts["logPath"] = str(log_path)

    result = {
        "jobId": job_id,
        "status": "completed",
        "symbol": payload.symbol.upper(),
        "timeframe": payload.timeframe,
        "parameters": payload.parameters,
        "submittedAt": base_job.get("submittedAt"),
        "startedAt": summary.get("state", {}).get("StartTime"),
        "endedAt": summary.get("state", {}).get("EndTime"),
        "capital": float(start_equity) if start_equity is not None else None,
        "netProfit": float(net_profit_dollars) if net_profit_dollars is not None else None,
        "netProfitPercent": net_profit_percent,
        "metrics": {k: v for k, v in metrics.items() if v is not None},
        "equityCurve": _extract_equity_curve(summary),
    "priceSeries": _extract_price_series(report, payload.symbol),
        "trades": _extract_trades(summary),
    "orders": _extract_orders(report),
        "indicators": indicators,
        "statistics": statistics,
        "runtimeStatistics": summary.get("runtimeStatistics", {}),
        "durationSeconds": duration_seconds,
        "artifacts": artifacts,
    }

    return result


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=f"Missing resource: {path}") from exc


ALGORITHMS: list[dict[str, Any]] = _load_json(ALGORITHMS_PATH)

JOB_STORE: Dict[str, Dict[str, Any]] = {}
EXECUTOR = ThreadPoolExecutor(max_workers=2)

app = FastAPI(title="QuantConnect Control Room API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class BacktestRequest(BaseModel):
    algorithmId: str = Field(..., description="Algorithm identifier from the manifest")
    symbol: str = Field(..., min_length=1, description="Ticker to run the backtest on")
    timeframe: str = Field(..., min_length=1, description="Chart timeframe (e.g., 1D, 1H)")
    startDate: Optional[str] = Field(None, description="ISO start date override")
    endDate: Optional[str] = Field(None, description="ISO end date override")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Algorithm-specific parameters")


@app.get("/algorithms")
def get_algorithms() -> list[dict[str, Any]]:
    return ALGORITHMS


@app.post("/backtests")
def submit_backtest(payload: BacktestRequest) -> dict[str, Any]:
    if not any(algo["id"] == payload.algorithmId for algo in ALGORITHMS):
        raise HTTPException(status_code=400, detail="Unknown algorithm id")

    job_id = str(uuid4())
    JOB_STORE[job_id] = {
        "jobId": job_id,
        "status": "queued",
        "symbol": payload.symbol.upper(),
        "timeframe": payload.timeframe,
        "parameters": payload.parameters,
        "submittedAt": time.time(),
    }

    EXECUTOR.submit(_run_backtest_job, job_id, payload)

    return {"jobId": job_id, "status": "queued"}


@app.get("/backtests/{job_id}")
def get_backtest(job_id: str) -> dict[str, Any]:
    result = JOB_STORE.get(job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return result


@app.get("/market-data")
def get_market_data(
    symbol: str = Query(..., min_length=1, description="Ticker symbol (e.g., SPY)"),
    timeframe: str = Query("1D", description="Requested timeframe"),
) -> dict[str, Any]:
    normalized_symbol = symbol.upper()
    normalized_timeframe = timeframe.lower()

    if normalized_symbol == "SPY" and normalized_timeframe in {"1d", "daily"}:
        candles = _load_json(SPY_SAMPLE_DATA_PATH)
        return {"symbol": normalized_symbol, "timeframe": "1D", "candles": candles}

    raise HTTPException(status_code=404, detail="Sample data not available for the requested symbol/timeframe")


@app.get("/")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


def _run_backtest_job(job_id: str, payload: BacktestRequest) -> None:
    JOB_STORE[job_id]["status"] = "running"
    try:
        job_env = _prepare_job_environment(job_id, payload)
        config_path: Path = job_env["config_path"]

        env = os.environ.copy()
        env.setdefault("PYTHONNET_PYDLL", _resolve_python_dll())

        if not LEAN_LAUNCHER_PATH.exists():
            raise RuntimeError(f"Lean launcher path not found: {LEAN_LAUNCHER_PATH}")

        command = [
            "dotnet",
            "run",
            "--project",
            str(LEAN_LAUNCHER_PATH),
            "--",
            "--config",
            str(config_path),
        ]

        start_time = time.time()
        process = subprocess.run(
            command,
            cwd=str(LEAN_LAUNCHER_PATH),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        duration = time.time() - start_time

        if process.returncode != 0:
            stderr = process.stderr.strip() or process.stdout.strip()
            raise RuntimeError(f"Lean exited with {process.returncode}: {stderr}")

        summary_path = next(job_env["job_dir"].glob("*-summary.json"), None)
        if not summary_path:
            raise RuntimeError("Lean backtest completed but no summary JSON was produced")

        report_path = summary_path.with_name(summary_path.name.replace("-summary", ""))

        result_payload = _build_backtest_result(
            job_id,
            payload,
            summary_path,
            report_path,
            job_env,
            lean_stdout=process.stdout,
            lean_stderr=process.stderr,
            duration_seconds=duration,
        )

        JOB_STORE[job_id] = result_payload
    except Exception as exc:  # pragma: no cover - defensive
        JOB_STORE[job_id] = {
            "jobId": job_id,
            "status": "error",
            "symbol": payload.symbol.upper(),
            "timeframe": payload.timeframe,
            "parameters": payload.parameters,
            "error": str(exc),
        }

