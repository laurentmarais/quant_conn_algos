import { createChart } from 'lightweight-charts'
import { useEffect, useMemo, useRef } from 'react'

const CHART_OPTIONS = {
  layout: {
    background: { color: 'transparent' },
    textColor: '#cbd5f5',
  },
  grid: {
    vertLines: { color: 'rgba(148, 163, 184, 0.15)' },
    horzLines: { color: 'rgba(148, 163, 184, 0.15)' },
  },
  rightPriceScale: {
    borderColor: 'rgba(148, 163, 184, 0.25)',
  },
  timeScale: {
    borderColor: 'rgba(148, 163, 184, 0.25)',
    timeVisible: true,
    secondsVisible: false,
  },
  crosshair: {
    mode: 0,
  },
}

function buildMarkers(trades) {
  if (!Array.isArray(trades)) return []
  const markers = []
  trades.forEach((trade) => {
    if (trade.entryTime) {
      markers.push({
        time: trade.entryTime,
        position: 'belowBar',
        color: '#22c55e',
        shape: 'arrowUp',
        text: `Buy ${trade.quantity ?? ''}`.trim(),
      })
    }
    if (trade.exitTime) {
      markers.push({
        time: trade.exitTime,
        position: 'aboveBar',
        color: '#ef4444',
        shape: 'arrowDown',
        text: `Sell ${trade.quantity ?? ''}`.trim(),
      })
    }
  })
  return markers
}

export default function PriceChart({ symbol, candles, trades }) {
  const containerRef = useRef(null)
  const chartRef = useRef(null)
  const seriesRef = useRef(null)

  const markers = useMemo(() => buildMarkers(trades), [trades])

  useEffect(() => {
    const container = containerRef.current
    if (!container) {
      return
    }

    const chart = createChart(container, {
      ...CHART_OPTIONS,
      width: container.clientWidth,
      height: 360,
    })
    chartRef.current = chart

    const series = chart.addCandlestickSeries({
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
      priceLineVisible: false,
    })
    seriesRef.current = series

    let observer
    if (typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(() => {
        if (container && chart) {
          chart.applyOptions({ width: container.clientWidth, height: 360 })
          chart.timeScale().fitContent()
        }
      })
      observer.observe(container)
    }

    return () => {
      observer?.disconnect()
      chart.remove()
    }
  }, [])

  useEffect(() => {
    if (!seriesRef.current) return
    const formatted = (candles ?? []).map((candle) => ({
      time: candle.time,
      open: Number(candle.open ?? 0),
      high: Number(candle.high ?? candle.open ?? 0),
      low: Number(candle.low ?? candle.open ?? 0),
      close: Number(candle.close ?? 0),
    }))
    seriesRef.current.setData(formatted)
    seriesRef.current.setMarkers(markers)
    chartRef.current?.timeScale().fitContent()
  }, [candles, markers])

  return (
    <div className="chart-wrapper">
      <header className="chart-header">
        <h3>{symbol} Price</h3>
      </header>
  <div ref={containerRef} className="chart-surface" style={{ height: 360 }} />
      {(!candles || !candles.length) && (
        <div className="chart-placeholder">Run a backtest to see price data.</div>
      )}
    </div>
  )
}
