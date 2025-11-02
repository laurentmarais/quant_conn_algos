from typing import Optional

from AlgorithmImports import *  # type: ignore


class RsiMaCrossAlgorithm(QCAlgorithm):
    def Initialize(self) -> None:
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2020, 1, 1)
        self.SetCash(100000)

        self.symbol = self.AddEquity("SPY", Resolution.Daily).Symbol

        self.rsi_period = 14
        self.rsi_ma_period = 10
        self.rsi = self.RSI(self.symbol, self.rsi_period, MovingAverageType.Wilders, Resolution.Daily)
        self.rsi_ma = SimpleMovingAverage(self.rsi_ma_period)

        self.prev_spread: Optional[float] = None

        self.SetWarmup(max(self.rsi_period, self.rsi_ma_period) * 3)

    def OnData(self, data: Slice) -> None:
        if not self.rsi.IsReady:
            return

        self.rsi_ma.Update(self.Time, self.rsi.Current.Value)
        if self.IsWarmingUp or not self.rsi_ma.IsReady:
            return

        spread = self.rsi.Current.Value - self.rsi_ma.Current.Value
        if self.prev_spread is None:
            self.prev_spread = spread
            return

        invested = self.Portfolio[self.symbol].Invested
        if self.prev_spread >= 0 and spread < 0 and not invested:
            self.SetHoldings(self.symbol, 1.0)
        elif self.prev_spread <= 0 and spread > 0 and invested:
            self.Liquidate(self.symbol)

        self.prev_spread = spread

        self.Plot("RSI", "RSI", self.rsi.Current.Value)
        self.Plot("RSI", "RSI_MA", self.rsi_ma.Current.Value)
