from typing import Optional, TYPE_CHECKING

from AlgorithmImports import *  # type: ignore

if TYPE_CHECKING:  # pragma: no cover - hints for tooling
    from AlgorithmImports import MovingAverageType, QCAlgorithm, Resolution, Slice  # type: ignore


class BollingerReversion(QCAlgorithm):
    def Initialize(self) -> None:
        self.SetStartDate(2016, 1, 1)
        self.SetEndDate(2021, 1, 1)
        self.SetCash(100000)

        symbol = self.GetParameter("symbol") or "IWM"
        timeframe = (self.GetParameter("timeframe") or "1D").upper()
        self.resolution = self._resolve_resolution(timeframe)

        self.symbol = self.AddEquity(symbol, self.resolution).Symbol  # type: ignore[name-defined]

        self.window = int(self.GetParameter("basisPeriod") or 20)
        self.std_dev = float(self.GetParameter("stdDev") or 2.0)
        self.exposure = float(self.GetParameter("exposure") or 0.75)
        self.rsi_period = int(self.GetParameter("rsiPeriod") or 14)

        self.bbands = self.BB(self.symbol, self.window, self.std_dev, MovingAverageType.Simple, self.resolution)
        self.rsi = self.RSI(self.symbol, self.rsi_period, MovingAverageType.Wilders, self.resolution)
        self.recent_low: Optional[float] = None

        self.SetWarmup(self.window * 3)

    def OnData(self, data: Slice) -> None:
        if self.IsWarmingUp:
            return
        if not (self.bbands.IsReady and self.rsi.IsReady):
            return

        price = self.Securities[self.symbol].Price
        invested = self.Portfolio[self.symbol].Invested

        lower = self.bbands.LowerBand.Current.Value
        upper = self.bbands.UpperBand.Current.Value
        middle = self.bbands.MiddleBand.Current.Value

        self.Plot("Bands", "Lower", lower)
        self.Plot("Bands", "Middle", middle)
        self.Plot("Bands", "Upper", upper)
        self.Plot("RSI", "RSI", self.rsi.Current.Value)

        if not invested and price < lower and self.rsi.Current.Value < 35:
            weight = max(min(self.exposure, 1.0), 0.0)
            self.SetHoldings(self.symbol, weight)
            self.recent_low = price
            return

        if invested:
            self.recent_low = price if self.recent_low is None else min(self.recent_low, price)
            if price > middle or self.rsi.Current.Value > 65:
                self.Liquidate(self.symbol)
                self.recent_low = None

    def _resolve_resolution(self, value: str) -> Resolution:
        normalized = value.replace(" ", "").upper()
        if normalized in {"1H", "60", "HOURLY"}:
            return Resolution.Hour  # type: ignore[name-defined]
        if normalized in {"15M", "15", "15MIN"}:
            return Resolution.Minute  # type: ignore[name-defined]
        return Resolution.Daily  # type: ignore[name-defined]
