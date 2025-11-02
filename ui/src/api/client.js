const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

async function request(path, options = {}) {
  const { parse = true, headers, ...rest } = options
  const joined = `${API_BASE_URL}${path}`
  const response = await fetch(joined, {
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
    ...rest,
  })

  if (!response.ok) {
    const message = await safeParseError(response)
    throw new Error(message)
  }

  if (!parse) {
    return undefined
  }

  return response.json()
}

async function safeParseError(response) {
  try {
    const data = await response.json()
    if (typeof data?.detail === 'string') {
      return data.detail
    }
  } catch (error) {
    // ignored – fallback to status text
  }
  return response.statusText || 'Request failed'
}

export async function fetchAlgorithms() {
  return request('/algorithms')
}

export async function createBacktest(payload) {
  return request('/backtests', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getBacktest(jobId) {
  return request(`/backtests/${jobId}`)
}

export async function fetchMarketData({ symbol, timeframe }) {
  const url = new URL(`${API_BASE_URL}/market-data`)
  url.searchParams.set('symbol', symbol)
  if (timeframe) {
    url.searchParams.set('timeframe', timeframe)
  }

  const response = await fetch(url.toString())
  if (!response.ok) {
    const message = await safeParseError(response)
    throw new Error(message)
  }

  return response.json()
}
