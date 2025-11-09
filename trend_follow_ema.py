from typing import Optional, TYPE_CHECKING

from AlgorithmImports import *  # type: ignore

if TYPE_CHECKING:  # pragma: no cover - hints for tooling
    from AlgorithmImports import MovingAverageType, QCAlgorithm, Resolution, Slice  # type: ignore


class EmaTrendFollower(QCAlgorithm):
    def Initialize(self) -> None:
        self.SetStartDate(2017, 1, 1)
        self.SetEndDate(2021, 1, 1)
        self.SetCash(100000)

        symbol = self.GetParameter("symbol") or "QQQ"
        timeframe = (self.GetParameter("timeframe") or "1D").upper()
        self.resolution = self._resolve_resolution(timeframe)

        self.symbol = self.AddEquity(symbol, self.resolution).Symbol  # type: ignore[name-defined]

        self.fast_period = int(self.GetParameter("fastPeriod") or 12)
        self.slow_period = int(self.GetParameter("slowPeriod") or 30)
        self.atr_period = int(self.GetParameter("atrPeriod") or 14)
        self.atr_multiplier = float(self.GetParameter("atrMultiplier") or 2.5)
        self.exposure = float(self.GetParameter("exposure") or 1.0)
        self.rsi_period = int(self.GetParameter("rsiPeriod") or 14)

        self.fast_ema = self.EMA(self.symbol, self.fast_period, self.resolution)
        self.slow_ema = self.EMA(self.symbol, self.slow_period, self.resolution)
        self.atr = self.ATR(self.symbol, self.atr_period, MovingAverageType.Wilders, self.resolution)
        self.rsi = self.RSI(self.symbol, self.rsi_period, MovingAverageType.Wilders, self.resolution)

        self.trailing_stop: Optional[float] = None

        self.SetWarmup(max(self.fast_period, self.slow_period, self.atr_period) * 3)

    def OnData(self, data: Slice) -> None:
        if self.IsWarmingUp:
            return
        if not (self.fast_ema.IsReady and self.slow_ema.IsReady and self.atr.IsReady and self.rsi.IsReady):
            return

        price = self.Securities[self.symbol].Price
        invested = self.Portfolio[self.symbol].Invested

        self.Plot("Trend", "FastEMA", self.fast_ema.Current.Value)
        self.Plot("Trend", "SlowEMA", self.slow_ema.Current.Value)
        self.Plot("RSI", "RSI", self.rsi.Current.Value)

        if not invested and self.fast_ema.Current.Value > self.slow_ema.Current.Value and self.rsi.Current.Value > 50:
            weight = max(min(self.exposure, 1.0), 0.0)
            self.SetHoldings(self.symbol, weight)
            self.trailing_stop = price - self.atr_multiplier * self.atr.Current.Value
            return

        if invested:
            if self.trailing_stop is None:
                self.trailing_stop = price - self.atr_multiplier * self.atr.Current.Value
            else:
                candidate = price - self.atr_multiplier * self.atr.Current.Value
                self.trailing_stop = max(self.trailing_stop, candidate)

            if self.fast_ema.Current.Value < self.slow_ema.Current.Value or price < (self.trailing_stop or price):
                self.Liquidate(self.symbol)
                self.trailing_stop = None

    def _resolve_resolution(self, value: str) -> Resolution:
        normalized = value.replace(" ", "").upper()
        if normalized in {"1H", "60", "HOURLY"}:
            return Resolution.Hour  # type: ignore[name-defined]
        if normalized in {"15M", "15", "15MIN"}:
            return Resolution.Minute  # type: ignore[name-defined]
        return Resolution.Daily  # type: ignore[name-defined]
