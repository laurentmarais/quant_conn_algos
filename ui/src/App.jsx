import { useEffect, useMemo, useState } from 'react'
import './App.css'
import { createBacktest, fetchAlgorithms, getBacktest } from './api/client'
import PriceChart from './components/PriceChart'
import TimeSeriesChart from './components/TimeSeriesChart'
import ParameterControls from './components/ParameterControls'
import { mockAlgorithms, mockBacktestResult } from './mock/data'

const timeframeOptions = [
  { id: '1D', label: '1D' },
  { id: '4H', label: '4H' },
  { id: '1H', label: '1H' },
  { id: '15m', label: '15m' },
]

const currencyFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
})

const percentFormatter = new Intl.NumberFormat('en-US', {
  style: 'percent',
  maximumFractionDigits: 1,
})

function cloneParameters(input) {
  if (!input) return {}
  return Object.fromEntries(
    Object.entries(input).map(([key, value]) => {
      if (value == null) {
        return [key, '']
      }
      if (typeof value === 'number') {
        return [key, String(value)]
      }
      return [key, value]
    })
  )
}

function coerceParameterTypes(currentValues, defaults = {}) {
  const result = {}

  Object.entries(defaults).forEach(([key, defaultValue]) => {
    const raw = currentValues?.[key]
    if (raw === undefined || raw === '') {
      result[key] = defaultValue
      return
    }

    if (typeof defaultValue === 'number') {
      const parsed = Number(raw)
      result[key] = Number.isFinite(parsed) ? parsed : defaultValue
    } else {
      result[key] = raw
    }
  })

  Object.entries(currentValues ?? {}).forEach(([key, raw]) => {
    if (result[key] !== undefined) {
      return
    }
    if (raw === '' || raw === undefined) {
      return
    }
    const numeric = Number(raw)
    if (Number.isFinite(numeric)) {
      result[key] = numeric
    } else {
      result[key] = raw
    }
  })

  return result
}

function App() {
  const [algorithms, setAlgorithms] = useState(mockAlgorithms)
  const [selectedAlgoId, setSelectedAlgoId] = useState(
    mockAlgorithms[0]?.id ?? ''
  )
  const [symbol, setSymbol] = useState(
    mockAlgorithms[0]?.defaults.symbol ?? 'SPY'
  )
  const [timeframe, setTimeframe] = useState(
    mockAlgorithms[0]?.defaults.timeframe ?? timeframeOptions[0].id
  )
  const [parameters, setParameters] = useState(
    () => cloneParameters(mockAlgorithms[0]?.defaults.parameters ?? {})
  )
  const [runState, setRunState] = useState('idle')
  const [activeTab, setActiveTab] = useState('chart')
  const [result, setResult] = useState(null)
  const [notice, setNotice] = useState('')

  useEffect(() => {
    let isCancelled = false

    async function loadAlgorithms() {
      try {
        const data = await fetchAlgorithms()
        if (isCancelled) return

        if (Array.isArray(data) && data.length) {
          const first = data[0]
          setAlgorithms(data)
          setSelectedAlgoId(first.id)
          setSymbol(first?.defaults?.symbol ?? 'SPY')
          setTimeframe(first?.defaults?.timeframe ?? timeframeOptions[0].id)
          setParameters(cloneParameters(first?.defaults?.parameters ?? {}))
          setRunState('idle')
          setResult(null)
          setNotice('')
        }
      } catch (error) {
        if (isCancelled) return

        setNotice(
          'Backend API unavailable. Displaying sample data until the service is running.'
        )
        setAlgorithms(mockAlgorithms)
        setParameters(
          cloneParameters(mockAlgorithms[0]?.defaults.parameters ?? {})
        )
        setResult(mockBacktestResult)
        setRunState('complete')
      }
    }

    loadAlgorithms()
    return () => {
      isCancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const selectedAlgo = useMemo(
    () => algorithms.find((algo) => algo.id === selectedAlgoId),
    [algorithms, selectedAlgoId]
  )

  const defaults = selectedAlgo?.defaults ?? {}
  const parameterDefaults = defaults.parameters ?? {}

  const handleParameterChange = (key, value) => {
    setParameters((prev) => ({
      ...prev,
      [key]: value,
    }))
  }

  const handleParameterReset = (key) => {
    const defaultValue = parameterDefaults[key]
    setParameters((prev) => ({
      ...prev,
      [key]:
        defaultValue === undefined || defaultValue === null
          ? ''
          : typeof defaultValue === 'number'
            ? String(defaultValue)
            : defaultValue,
    }))
  }

  const handleParameterResetAll = () => {
    setParameters(cloneParameters(parameterDefaults))
  }

  const handleRun = async () => {
    if (!selectedAlgoId) {
      setNotice('Select an algorithm before running a backtest.')
      return
    }

    setActiveTab('chart')
    setRunState('running')
    setNotice('')

    const payload = {
      algorithmId: selectedAlgoId,
      symbol: symbol.trim().toUpperCase(),
      timeframe,
      startDate: defaults.startDate,
      endDate: defaults.endDate,
      parameters: coerceParameterTypes(parameters, parameterDefaults),
    }

    try {
      const { jobId } = await createBacktest(payload)
      const jobResult = await pollBacktest(jobId)
      setResult(jobResult)
      setRunState(jobResult?.status ?? 'complete')
    } catch (error) {
      console.error('Backtest execution failed', error)
      setResult(mockBacktestResult)
      setRunState('error')
      setNotice(
        'Backtest service unavailable. Displaying cached sample output until the service is online.'
      )
    }
  }

  async function pollBacktest(jobId, attempts = 8, delayMs = 400) {
    for (let attempt = 0; attempt < attempts; attempt += 1) {
      const job = await getBacktest(jobId)
      if (!job?.status || job.status === 'completed') {
        return job
      }
      await new Promise((resolve) => setTimeout(resolve, delayMs))
    }
    throw new Error('Timed out waiting for backtest to finish')
  }

  const runButtonLabel =
    runState === 'running' ? 'Running Backtest…' : 'Run Backtest'

  const metrics = result?.metrics
    ? [
        {
          label: 'Net P&L',
          value: currencyFormatter.format(result.netProfit ?? 0),
        },
        result?.netProfitPercent != null
          ? {
              label: 'Net %',
              value: percentFormatter.format(result.netProfitPercent),
            }
          : null,
        {
          label: 'Win Rate',
          value: percentFormatter.format(result.metrics.winRate ?? 0),
        },
        {
          label: 'Total Trades',
          value: result.metrics.totalTrades ?? 0,
        },
        {
          label: 'Max Drawdown',
          value: percentFormatter.format(result.metrics.maxDrawdown ?? 0),
        },
      ].filter(Boolean)
    : []

  return (
    <div className="app-shell">
      {notice && <div className="notice">{notice}</div>}
      <Toolbar
        algorithms={algorithms}
        selectedAlgoId={selectedAlgoId}
        symbol={symbol}
        timeframe={timeframe}
        runState={runState}
        onAlgoChange={(id) => {
          setSelectedAlgoId(id)
          const next = algorithms.find((algo) => algo.id === id)
          if (next?.defaults) {
            setSymbol(next.defaults.symbol ?? symbol)
            setTimeframe(next.defaults.timeframe ?? timeframeOptions[0].id)
            setParameters(cloneParameters(next.defaults.parameters ?? {}))
          }
        }}
        onSymbolChange={(value) => setSymbol(value.toUpperCase())}
        onTimeframeChange={setTimeframe}
        onRun={handleRun}
        timeframes={timeframeOptions}
        runLabel={runButtonLabel}
      />

      <div className="app-content">
        <section className="panel primary-panel">
          <TabList activeTab={activeTab} onChange={setActiveTab} />
          <div className="panel-body">
            {activeTab === 'chart' && (
              <PriceChart
                symbol={result?.symbol ?? symbol}
                candles={result?.priceSeries ?? []}
                trades={result?.trades ?? []}
              />
            )}

            {activeTab === 'equity' && (
              <div className="chart-wrapper">
                <header className="chart-header">
                  <h3>Equity Curve</h3>
                </header>
                <TimeSeriesChart
                  data={result?.equityCurve ?? []}
                  type="area"
                  color="#38bdf8"
                  height={320}
                  yAxisFormatter={(value) => currencyFormatter.format(value)}
                />
              </div>
            )}

            {activeTab === 'trades' && (
              <TradesTable trades={result?.trades ?? []} />
            )}

            {activeTab === 'orders' && (
              <OrdersTable orders={result?.orders ?? []} />
            )}

            {activeTab === 'indicators' && (
              <IndicatorsPanel indicators={result?.indicators ?? []} />
            )}

            {activeTab === 'metrics' && (
              <MetricGrid items={metrics} />
            )}
          </div>
        </section>

        <aside className="panel secondary-panel">
          <h2>{selectedAlgo?.name ?? 'Select an algorithm'}</h2>
          <p className="algo-description">{selectedAlgo?.description}</p>

          <ParameterControls
            parameters={parameters}
            defaults={parameterDefaults}
            onChange={handleParameterChange}
            onReset={handleParameterReset}
            onResetAll={handleParameterResetAll}
            disabled={runState === 'running'}
          />

          <div className="summary-block">
            <span className="summary-label">Run status</span>
            <span className={`status-pill status-${runState}`}>
              {runState === 'running' && 'Running'}
              {runState === 'idle' && 'Idle'}
              {runState === 'complete' && 'Complete'}
              {runState === 'error' && 'Error'}
            </span>
          </div>

          <div className="summary-block">
            <span className="summary-label">Symbol</span>
            <span>{result?.symbol ?? symbol}</span>
          </div>

          <div className="summary-block">
            <span className="summary-label">Timeframe</span>
            <span>{result?.timeframe ?? timeframe}</span>
          </div>

          <div className="summary-block">
            <span className="summary-label">Sample period</span>
            <span>
              {result?.startedAt && result?.endedAt
                ? `${result.startedAt} → ${result.endedAt}`
                : 'Pending'}
            </span>
          </div>

          <div className="metric-list">
            <MetricGrid items={metrics} />
          </div>
        </aside>
      </div>
    </div>
  )
}

function Toolbar({
  algorithms,
  selectedAlgoId,
  symbol,
  timeframe,
  timeframes,
  runState,
  runLabel,
  onAlgoChange,
  onSymbolChange,
  onTimeframeChange,
  onRun,
}) {
  return (
    <header className="toolbar">
      <div className="toolbar-section">
        <h1 className="app-title">QuantConnect Control Room</h1>
      </div>

      <div className="toolbar-section">
        <label className="field">
          <span className="field-label">Algorithm</span>
          <select
            value={selectedAlgoId}
            onChange={(event) => onAlgoChange(event.target.value)}
          >
            {algorithms.map((algo) => (
              <option key={algo.id} value={algo.id}>
                {algo.name}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span className="field-label">Symbol</span>
          <input
            value={symbol}
            onChange={(event) => onSymbolChange(event.target.value)}
            placeholder="SPY"
          />
        </label>

        <div className="field">
          <span className="field-label">Timeframe</span>
          <div className="timeframe-group">
            {timeframes.map((item) => (
              <button
                key={item.id}
                className={`timeframe-button ${
                  timeframe === item.id ? 'active' : ''
                }`}
                onClick={() => onTimeframeChange(item.id)}
                type="button"
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="toolbar-section">
        <button
          className="run-button"
          type="button"
          onClick={onRun}
          disabled={runState === 'running'}
        >
          {runLabel}
        </button>
      </div>
    </header>
  )
}

function TabList({ activeTab, onChange }) {
  const tabs = [
    { id: 'chart', label: 'Price & Trades' },
    { id: 'equity', label: 'Equity' },
    { id: 'trades', label: 'Trades' },
    { id: 'orders', label: 'Orders' },
    { id: 'indicators', label: 'Indicators' },
    { id: 'metrics', label: 'Metrics' },
  ]

  return (
    <nav className="tab-list">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          className={`tab-button ${activeTab === tab.id ? 'active' : ''}`}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  )
}

function TradesTable({ trades }) {
  if (!trades.length) {
    return <div className="placeholder">No trades to display yet.</div>
  }

  return (
    <div className="trades-table-wrapper">
      <table className="trades-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Direction</th>
            <th>Entry</th>
            <th>Exit</th>
            <th>Qty</th>
            <th>P&L</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((trade) => (
            <tr key={trade.id}>
              <td>{trade.id}</td>
              <td>{trade.direction}</td>
              <td>
                <div>{trade.entryTime}</div>
                <span className="muted">
                  ${Number(trade.entryPrice ?? 0).toFixed(2)}
                </span>
              </td>
              <td>
                <div>{trade.exitTime}</div>
                <span className="muted">
                  ${Number(trade.exitPrice ?? 0).toFixed(2)}
                </span>
              </td>
              <td>{trade.quantity}</td>
              <td className={trade.profit >= 0 ? 'profit' : 'loss'}>
                {currencyFormatter.format(trade.profit)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function OrdersTable({ orders }) {
  if (!orders.length) {
    return <div className="placeholder">No orders captured yet.</div>
  }

  return (
    <div className="trades-table-wrapper">
      <table className="trades-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Time</th>
            <th>Status</th>
            <th>Type</th>
            <th>Direction</th>
            <th>Qty</th>
            <th>Price</th>
            <th>Tag</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((order) => (
            <tr key={order.id}>
              <td>{order.id}</td>
              <td>{order.time ?? '—'}</td>
              <td>{order.status ?? '—'}</td>
              <td>{order.type ?? '—'}</td>
              <td>{order.direction ?? '—'}</td>
              <td>{order.quantity ?? '—'}</td>
              <td>
                {order.price != null
                  ? currencyFormatter.format(order.price)
                  : '—'}
              </td>
              <td>{order.tag || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function IndicatorsPanel({ indicators }) {
  if (!Array.isArray(indicators) || !indicators.length) {
    return <div className="placeholder">Indicators will appear here.</div>
  }

  const usable = indicators.filter((item) => Array.isArray(item?.data) && item.data.length)
  if (!usable.length) {
    return <div className="placeholder">Indicators will appear here.</div>
  }

  const palette = ['#38bdf8', '#f97316', '#34d399', '#a855f7', '#facc15']

  return (
    <div className="indicator-grid">
      {usable.map((indicator, index) => (
        <div key={indicator.id ?? `${indicator.chart}-${indicator.series}-${index}`} className="chart-wrapper">
          <header className="chart-header">
            <h3>{indicator.label ?? `${indicator.chart} · ${indicator.series}`}</h3>
          </header>
          <TimeSeriesChart
            data={indicator.data ?? []}
            color={palette[index % palette.length]}
            height={240}
          />
        </div>
      ))}
    </div>
  )
}

function MetricGrid({ items }) {
  if (!items.length) {
    return <div className="placeholder">Metrics will populate after a run.</div>
  }

  return (
    <div className="metric-grid">
      {items.map((item) => (
        <div key={item.label} className="metric-card">
          <span className="metric-label">{item.label}</span>
          <span className="metric-value">{item.value}</span>
        </div>
      ))}
    </div>
  )
}

export default App
