from __future__ import annotations

import copy
import json
import time
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
SAMPLE_BACKTEST_PATH = ROOT / "sample_backtest.json"
SPY_SAMPLE_DATA_PATH = PROJECT_ROOT / "results/spy_daily_2016_2020.json"


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=f"Missing resource: {path}") from exc


ALGORITHMS: list[dict[str, Any]] = _load_json(ALGORITHMS_PATH)
SAMPLE_BACKTEST: dict[str, Any] = _load_json(SAMPLE_BACKTEST_PATH)

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
        time.sleep(0.5)
        JOB_STORE[job_id] = _build_sample_result(job_id, payload)
    except Exception as exc:  # pragma: no cover - defensive
        JOB_STORE[job_id] = {
            "jobId": job_id,
            "status": "error",
            "symbol": payload.symbol.upper(),
            "timeframe": payload.timeframe,
            "parameters": payload.parameters,
            "error": str(exc),
        }


def _build_sample_result(job_id: str, payload: BacktestRequest) -> dict[str, Any]:
    sample = copy.deepcopy(SAMPLE_BACKTEST)
    sample.update(
        {
            "jobId": job_id,
            "status": "completed",
            "symbol": payload.symbol.upper(),
            "timeframe": payload.timeframe,
            "parameters": payload.parameters,
        }
    )
    return sample
