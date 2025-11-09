import json
from collections.abc import Iterator
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from fastapi.testclient import TestClient

import backend.app as app_module


@pytest.fixture(autouse=True)
def reset_job_store() -> Iterator[None]:
    app_module.JOB_STORE.clear()
    yield
    app_module.JOB_STORE.clear()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app_module.app)


class DummyExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, tuple[Any, ...], dict[str, Any]]] = []

    def submit(self, func: Any, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - simple stub
        self.calls.append((func, args, kwargs))
        return None


def test_healthcheck_returns_ok(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_algorithms_returns_manifest(client: TestClient) -> None:
    response = client.get("/algorithms")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data
    assert {item["id"] for item in data} == {algo["id"] for algo in app_module.ALGORITHMS}


def test_market_data_returns_spy_sample(client: TestClient) -> None:
    response = client.get("/market-data", params={"symbol": "spy", "timeframe": "1D"})
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "SPY"
    assert data["timeframe"] == "1D"
    assert len(data["candles"]) > 0


def test_market_data_unknown_symbol(client: TestClient) -> None:
    response = client.get("/market-data", params={"symbol": "qqq", "timeframe": "1D"})
    assert response.status_code == 404


def test_submit_backtest_rejects_unknown_algorithm(client: TestClient) -> None:
    payload = {
        "algorithmId": "missing",
        "symbol": "SPY",
        "timeframe": "1D",
    }
    response = client.post("/backtests", json=payload)
    assert response.status_code == 400


def test_submit_backtest_queues_job(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    dummy_executor = DummyExecutor()
    monkeypatch.setattr(app_module, "EXECUTOR", dummy_executor)

    payload = {
        "algorithmId": app_module.ALGORITHMS[0]["id"],
        "symbol": "SPY",
        "timeframe": "1D",
        "parameters": {"foo": "bar"},
    }

    response = client.post("/backtests", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["jobId"] in app_module.JOB_STORE
    job_record = app_module.JOB_STORE[data["jobId"]]
    assert job_record["status"] == "queued"
    assert job_record["symbol"] == "SPY"
    assert dummy_executor.calls
    func, args, kwargs = dummy_executor.calls[0]
    assert func is app_module._run_backtest_job
    assert isinstance(args[1], app_module.BacktestRequest)


def test_prepare_job_environment_injects_parameters(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    monkeypatch.setattr(app_module, "BACKTEST_STORAGE_ROOT", storage_root)

    payload = app_module.BacktestRequest(
        algorithmId=app_module.ALGORITHMS[0]["id"],
        symbol="SPY",
        timeframe="1D",
        parameters={"foo": "bar"},
    )

    env = app_module._prepare_job_environment("job-1", payload)
    config_data = json.loads(Path(env["config_path"]).read_text())

    assert config_data["parameters"]["symbol"] == "SPY"
    assert config_data["parameters"]["timeframe"] == "1D"
    assert config_data["parameters"]["foo"] == "bar"


def test_parse_decimal_handles_various_inputs() -> None:
    parse = app_module._parse_decimal
    assert parse(10) == app_module.Decimal("10")
    assert parse("$1,234.50") == app_module.Decimal("1234.50")
    assert parse("12.5%") == app_module.Decimal("12.5")
    assert parse(" ") is None


def test_extract_price_series_returns_ohlc() -> None:
    report = {
        "charts": {
            "SPY": {
                "series": {
                    "Price": {
                        "values": [
                            [1609459200, "100", "102", "99", "101"],
                            [1609545600, 101, 105, 100, 104],
                        ]
                    }
                }
            }
        }
    }

    result = app_module._extract_price_series(report, "spy")
    assert len(result) == 2
    assert result[0] == {
        "time": "2021-01-01",
        "open": 100.0,
        "high": 102.0,
        "low": 99.0,
        "close": 101.0,
    }


def test_extract_orders_normalizes_fields() -> None:
    report = {
        "orders": {
            "1": {
                "id": 1,
                "symbol": {"value": "SPY"},
                "time": "2021-01-01T00:00:00Z",
                "type": 1,
                "direction": 0,
                "status": 3,
                "quantity": 10,
                "price": "101.5",
                "lastFillTime": "2021-01-01T01:00:00Z",
                "tag": "entry",
            }
        }
    }

    result = app_module._extract_orders(report)
    assert result == [
        {
            "id": 1,
            "symbol": "SPY",
            "time": "2021-01-01",
            "type": "Limit",
            "direction": "Buy",
            "status": "Filled",
            "quantity": 10,
            "price": 101.5,
            "lastFillTime": "2021-01-01",
            "tag": "entry",
        }
    ]


def test_extract_indicator_series_returns_rsi_values() -> None:
    report = {
        "charts": {
            "RSI": {
                "series": {
                    "RSI": {"values": [[1609459200, "50"], [1609545600, "55"]]},
                    "RSI_MA": {"values": [[1609459200, "48"], [1609545600, "52"]]},
                }
            }
        }
    }
    indicators = app_module._extract_indicator_series(report, "SPY")
    assert indicators
    indicator_map = {item["series"]: item for item in indicators}
    assert indicator_map["RSI"]["data"][0]["value"] == 50.0
    assert indicator_map["RSI_MA"]["data"][1]["value"] == 52.0


def test_extract_trades_formats_summary() -> None:
    summary = {
        "totalPerformance": {
            "closedTrades": [
                {
                    "direction": 0,
                    "entryTime": "2021-01-01T00:00:00Z",
                    "exitTime": "2021-01-05T00:00:00Z",
                    "entryPrice": 100,
                    "exitPrice": 105,
                    "quantity": 10,
                    "profitLoss": 50,
                }
            ]
        }
    }

    trades = app_module._extract_trades(summary)
    assert trades == [
        {
            "id": 1,
            "direction": "Long",
            "entryTime": "2021-01-01",
            "exitTime": "2021-01-05",
            "entryPrice": 100.0,
            "exitPrice": 105.0,
            "quantity": 10,
            "profit": 50.0,
        }
    ]


def test_run_backtest_job_happy_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    job_id = "job-123"
    payload = app_module.BacktestRequest(
        algorithmId=app_module.ALGORITHMS[0]["id"],
        symbol="SPY",
        timeframe="1D",
        parameters={"rsiPeriod": 14},
    )

    launcher_path = tmp_path / "launcher"
    launcher_path.mkdir()
    monkeypatch.setattr(app_module, "LEAN_LAUNCHER_PATH", launcher_path)
    monkeypatch.setattr(app_module, "_resolve_python_dll", lambda: "dummy-dll")

    job_dir = tmp_path / "job-dir"

    summary_payload = {
        "state": {"StartTime": "2020-01-01", "EndTime": "2020-01-02"},
        "totalPerformance": {
            "closedTrades": [
                {
                    "direction": 0,
                    "entryTime": "2020-01-01T00:00:00Z",
                    "exitTime": "2020-01-02T00:00:00Z",
                    "entryPrice": 100,
                    "exitPrice": 101,
                    "quantity": 1,
                    "profitLoss": 100,
                }
            ],
            "tradeStatistics": {
                "totalNumberOfTrades": 1,
                "numberOfWinningTrades": 1,
                "numberOfLosingTrades": 0,
                "totalProfitLoss": "100",
            },
            "portfolioStatistics": {"startEquity": "100000"},
        },
        "statistics": {
            "Net Profit": "1%",
            "Win Rate": "100%",
            "Drawdown": "10%",
            "Sharpe Ratio": "1.5",
            "Sortino Ratio": "1.2",
        },
        "runtimeStatistics": {},
    }

    report_payload = {
        "charts": {
            "SPY": {
                "series": {
                    "Price": {
                        "values": [
                            [1609459200, "100", "101", "99", "101"],
                        ]
                    }
                }
            },
            "RSI": {
                "series": {
                    "RSI": {"values": [[1609459200, "50"]]},
                    "RSI_MA": {"values": [[1609459200, "48"]]},
                }
            },
        },
        "orders": {
            "1": {
                "id": 1,
                "symbol": {"value": "SPY"},
                "time": "2020-01-01T00:00:00Z",
                "type": 1,
                "direction": 0,
                "status": 3,
                "quantity": 1,
                "price": "101",
                "lastFillTime": "2020-01-01T01:00:00Z",
                "tag": "entry",
            }
        },
    }

    def fake_prepare(job_id_arg: str, payload_arg: app_module.BacktestRequest) -> dict[str, Any]:
        assert job_id_arg == job_id
        assert payload_arg.symbol == "SPY"
        job_dir.mkdir()
        config_path = job_dir / "lean-config.json"
        config_path.write_text("{}")
        (job_dir / "result-summary.json").write_text(json.dumps(summary_payload))
        (job_dir / "result.json").write_text(json.dumps(report_payload))
        return {"job_dir": job_dir, "config_path": config_path, "algorithm_manifest": {}}

    def fake_run(*_args: Any, **_kwargs: Any) -> CompletedProcess[str]:
        return CompletedProcess(args=["dotnet"], returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(app_module, "_prepare_job_environment", fake_prepare)
    monkeypatch.setattr(app_module.subprocess, "run", fake_run)

    app_module.JOB_STORE[job_id] = {
        "jobId": job_id,
        "status": "queued",
        "symbol": "SPY",
        "timeframe": "1D",
        "parameters": payload.parameters,
    }

    app_module._run_backtest_job(job_id, payload)

    result = app_module.JOB_STORE[job_id]
    assert result["status"] == "completed"
    assert result["netProfit"] == 100.0
    assert result["netProfitPercent"] == 0.01
    assert result["metrics"]["totalTrades"] == 1
    assert result["priceSeries"][0]["close"] == 101.0
    assert result["orders"][0]["status"] == "Filled"
    indicator_map = {item["series"]: item for item in result["indicators"]}
    assert indicator_map["RSI"]["data"][0]["value"] == 50.0
    assert "summaryPath" in result["artifacts"]


def test_run_backtest_job_handles_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    job_id = "job-fail"
    payload = app_module.BacktestRequest(
        algorithmId=app_module.ALGORITHMS[0]["id"],
        symbol="SPY",
        timeframe="1D",
    )

    launcher_path = tmp_path / "launcher"
    launcher_path.mkdir()
    monkeypatch.setattr(app_module, "LEAN_LAUNCHER_PATH", launcher_path)
    monkeypatch.setattr(app_module, "_resolve_python_dll", lambda: "dummy-dll")

    job_dir = tmp_path / "job-fail"

    def fake_prepare(job_id_arg: str, _payload: app_module.BacktestRequest) -> dict[str, Any]:
        assert job_id_arg == job_id
        job_dir.mkdir()
        config_path = job_dir / "lean-config.json"
        config_path.write_text("{}")
        return {"job_dir": job_dir, "config_path": config_path, "algorithm_manifest": {}}

    def fake_run(*_args: Any, **_kwargs: Any) -> CompletedProcess[str]:
        return CompletedProcess(args=["dotnet"], returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(app_module, "_prepare_job_environment", fake_prepare)
    monkeypatch.setattr(app_module.subprocess, "run", fake_run)

    app_module.JOB_STORE[job_id] = {
        "jobId": job_id,
        "status": "queued",
        "symbol": "SPY",
        "timeframe": "1D",
        "parameters": {},
    }

    app_module._run_backtest_job(job_id, payload)

    result = app_module.JOB_STORE[job_id]
    assert result["status"] == "error"
    assert "Lean exited" in result["error"]
