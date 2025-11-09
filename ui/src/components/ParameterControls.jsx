function formatLabel(key) {
  return key
    .replace(/([A-Z])/g, ' $1')
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/^\w/, (char) => char.toUpperCase())
}

export default function ParameterControls({
  parameters,
  defaults,
  onChange,
  onReset,
  onResetAll,
  disabled = false,
}) {
  const entries = Object.entries(defaults ?? {})
  if (!entries.length) {
    return null
  }

  return (
    <section className="parameter-controls">
      <header className="parameter-header">
        <h3>Strategy Parameters</h3>
        {onResetAll && (
          <button
            type="button"
            className="parameter-reset-all"
            onClick={onResetAll}
            disabled={disabled}
          >
            Reset All
          </button>
        )}
      </header>

      <div className="parameter-list">
        {entries.map(([key, defaultValue]) => {
          const current = parameters?.[key] ?? ''
          const isNumericDefault = typeof defaultValue === 'number'
          const isIntegerDefault = Number.isInteger(defaultValue)

          return (
            <label key={key} className="parameter-row">
              <div className="parameter-label">
                <span>{formatLabel(key)}</span>
                <span className="parameter-default">Default: {String(defaultValue)}</span>
              </div>
              <div className="parameter-input-group">
                <input
                  type={isNumericDefault ? 'number' : 'text'}
                  step={isNumericDefault ? (isIntegerDefault ? 1 : 'any') : undefined}
                  inputMode={isNumericDefault ? 'decimal' : undefined}
                  value={current}
                  onChange={(event) => onChange?.(key, event.target.value)}
                  placeholder={String(defaultValue)}
                  disabled={disabled}
                />
                {onReset && (
                  <button
                    type="button"
                    className="parameter-reset"
                    onClick={() => onReset(key)}
                    disabled={disabled}
                  >
                    Reset
                  </button>
                )}
              </div>
            </label>
          )
        })}
      </div>
    </section>
  )
}
