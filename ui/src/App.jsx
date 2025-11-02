import { useEffect, useMemo, useState } from 'react'
import './App.css'
import { createBacktest, fetchAlgorithms, getBacktest } from './api/client'
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
      parameters: defaults.parameters ?? {},
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
              <PriceTable
                symbol={result?.symbol ?? symbol}
                candles={result?.priceSeries ?? []}
              />
            )}

            {activeTab === 'equity' && (
              <SeriesList
                title="Equity Curve"
                data={result?.equityCurve ?? []}
                valueFormatter={(point) =>
                  `${point.time}: ${currencyFormatter.format(point.value ?? 0)}`
                }
              />
            )}

            {activeTab === 'trades' && (
              <TradesTable trades={result?.trades ?? []} />
            )}

            {activeTab === 'orders' && (
              <OrdersTable orders={result?.orders ?? []} />
            )}

            {activeTab === 'indicators' && (
              <IndicatorsPanel indicators={result?.indicators ?? {}} />
            )}

            {activeTab === 'metrics' && (
              <MetricGrid items={metrics} />
            )}
          </div>
        </section>

        <aside className="panel secondary-panel">
          <h2>{selectedAlgo?.name ?? 'Select an algorithm'}</h2>
          <p className="algo-description">{selectedAlgo?.description}</p>

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

function SeriesList({ title, data, valueFormatter }) {
  if (!data.length) {
    return <div className="placeholder">No data available yet.</div>
  }

  return (
    <div className="series-list">
      <h3>{title}</h3>
      <ul>
        {data.map((point) => (
          <li key={`${title}-${point.time}`}>{valueFormatter(point)}</li>
        ))}
      </ul>
    </div>
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

function PriceTable({ symbol, candles }) {
  if (!candles.length) {
    return <div className="placeholder">Run a backtest to see price data.</div>
  }

  const rows = candles.slice(-200)

  return (
    <div className="trades-table-wrapper">
      <table className="trades-table">
        <thead>
          <tr>
            <th colSpan={5}>{symbol} Candles (most recent 200)</th>
          </tr>
          <tr>
            <th>Date</th>
            <th>Open</th>
            <th>High</th>
            <th>Low</th>
            <th>Close</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((candle) => (
            <tr key={candle.time}>
              <td>{candle.time}</td>
              <td>{Number(candle.open ?? 0).toFixed(2)}</td>
              <td>{Number(candle.high ?? candle.open ?? 0).toFixed(2)}</td>
              <td>{Number(candle.low ?? candle.open ?? 0).toFixed(2)}</td>
              <td>{Number(candle.close ?? 0).toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function IndicatorsPanel({ indicators }) {
  const rsi = indicators?.rsi ?? []
  const rsiSma = indicators?.rsiSma ?? []

  if (!rsi.length && !rsiSma.length) {
    return <div className="placeholder">Indicators will appear here.</div>
  }

  return (
    <div className="indicators-grid">
      <SeriesList
        title="RSI"
        data={rsi}
        valueFormatter={(point) =>
          `${point.time}: ${(point.value ?? 0).toFixed(1)}`
        }
      />
      <SeriesList
        title="RSI Moving Average"
        data={rsiSma}
        valueFormatter={(point) =>
          `${point.time}: ${(point.value ?? 0).toFixed(1)}`
        }
      />
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
