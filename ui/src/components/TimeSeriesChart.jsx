import { createChart } from 'lightweight-charts'
import { useEffect, useRef } from 'react'

function withAlpha(hex, alpha) {
  if (!hex || hex[0] !== '#' || (hex.length !== 7 && hex.length !== 4)) {
    return hex
  }
  let r
  let g
  let b
  if (hex.length === 7) {
    r = parseInt(hex.slice(1, 3), 16)
    g = parseInt(hex.slice(3, 5), 16)
    b = parseInt(hex.slice(5, 7), 16)
  } else {
    r = parseInt(hex[1] + hex[1], 16)
    g = parseInt(hex[2] + hex[2], 16)
    b = parseInt(hex[3] + hex[3], 16)
  }
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

const SHARED_OPTIONS = {
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

export default function TimeSeriesChart({
  data,
  type = 'line',
  color = '#38bdf8',
  height = 280,
  markers,
  yAxisFormatter,
}) {
  const containerRef = useRef(null)
  const chartRef = useRef(null)
  const seriesRef = useRef(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const chart = createChart(container, {
      ...SHARED_OPTIONS,
      width: container.clientWidth,
      height,
    })
    chartRef.current = chart

    let series
    if (type === 'area') {
      series = chart.addAreaSeries({
        lineColor: color,
        topColor: withAlpha(color, 0.35),
        bottomColor: withAlpha(color, 0.05),
        lineWidth: 2,
      })
    } else {
      series = chart.addLineSeries({
        color,
        lineWidth: 2,
      })
    }
    if (yAxisFormatter) {
      series.applyOptions({ priceFormat: { type: 'custom', formatter: yAxisFormatter } })
    }
    seriesRef.current = series

    let observer
    if (typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(() => {
        if (container && chart) {
          chart.applyOptions({ width: container.clientWidth, height })
          chart.timeScale().fitContent()
        }
      })
      observer.observe(container)
    }

    return () => {
      observer?.disconnect()
      chart.remove()
    }
  }, [color, height, type, yAxisFormatter])

  useEffect(() => {
    if (!seriesRef.current) return
    const formatted = (data ?? []).map((point) => ({ time: point.time, value: point.value }))
    seriesRef.current.setData(formatted)
    seriesRef.current.setMarkers(markers && markers.length ? markers : [])
    chartRef.current?.timeScale().fitContent()
  }, [data, markers])

  return <div ref={containerRef} className="chart-surface" style={{ height }} />
}
