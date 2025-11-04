import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import {
  fetchAlgorithms,
  createBacktest,
  getBacktest,
  fetchMarketData,
} from './client'

const API_BASE = 'http://localhost:8000'

function buildResponse({ ok = true, status = 200, statusText = 'OK', body = undefined } = {}) {
  return {
    ok,
    status,
    statusText,
    json: vi.fn().mockResolvedValue(body),
  }
}

describe('api/client', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('fetchAlgorithms returns manifest payload', async () => {
    const payload = [{ id: 'algo', name: 'Algo' }]
    fetch.mockResolvedValueOnce(buildResponse({ body: payload }))

    const result = await fetchAlgorithms()

    expect(fetch).toHaveBeenCalledWith(`${API_BASE}/algorithms`, expect.objectContaining({
      headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
    }))
    expect(result).toEqual(payload)
  })

  it('createBacktest posts payload and returns response', async () => {
    const payload = { algorithmId: 'algo', symbol: 'SPY' }
    const responseBody = { jobId: '123', status: 'queued' }
    fetch.mockResolvedValueOnce(buildResponse({ body: responseBody }))

    const result = await createBacktest(payload)

    expect(fetch).toHaveBeenCalledWith(`${API_BASE}/backtests`, expect.objectContaining({
      method: 'POST',
      body: JSON.stringify(payload),
    }))
    expect(result).toEqual(responseBody)
  })

  it('getBacktest fetches job by id', async () => {
    const jobId = 'job-1'
    const responseBody = { jobId, status: 'completed' }
    fetch.mockResolvedValueOnce(buildResponse({ body: responseBody }))

    const result = await getBacktest(jobId)

    expect(fetch).toHaveBeenCalledWith(`${API_BASE}/backtests/${jobId}`, expect.any(Object))
    expect(result).toEqual(responseBody)
  })

  it('fetchMarketData includes query params and returns JSON', async () => {
    const responseBody = { symbol: 'SPY', timeframe: '1D', candles: [] }
    fetch.mockResolvedValueOnce(buildResponse({ body: responseBody }))

    const result = await fetchMarketData({ symbol: 'SPY', timeframe: '1D' })

    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/market-data?symbol=SPY&timeframe=1D`
    )
    expect(result).toEqual(responseBody)
  })

  it('request helpers surface backend error detail', async () => {
    fetch.mockResolvedValueOnce(
      buildResponse({ ok: false, status: 404, statusText: 'Not Found', body: { detail: 'missing' } })
    )

    await expect(fetchAlgorithms()).rejects.toThrow('missing')
  })

  it('fetchMarketData falls back to status text on error without detail', async () => {
    fetch.mockResolvedValueOnce(
      buildResponse({ ok: false, status: 500, statusText: 'Server Error', body: {} })
    )

    await expect(fetchMarketData({ symbol: 'QQQ', timeframe: '1D' })).rejects.toThrow('Server Error')
  })
})
