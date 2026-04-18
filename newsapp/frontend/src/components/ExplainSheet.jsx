import { useState } from 'react'
import { fetchExplanation } from './api'
import { useApiKey } from './ApiKeyContext'

const MODES = [
  { key: 'explain', label: 'Explain', desc: 'Clear explanation' },
  { key: 'simplify', label: 'Simplify', desc: 'Plain language' },
  { key: 'expand', label: 'Expand', desc: 'More context' },
]

export default function ExplainSheet({ passage, articleTitle, onClose }) {
  const { apiKey } = useApiKey()
  const [mode, setMode] = useState('explain')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleExplain = async (selectedMode) => {
    setMode(selectedMode)
    setLoading(true)
    setResult(null)
    try {
      const data = await fetchExplanation(passage, articleTitle, selectedMode, apiKey)
      setResult(data.explanation)
    } catch {
      setResult('Unable to generate explanation.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <div className="overlay" onClick={onClose} />
      <div className="bottom-sheet px-5 pt-2 pb-8">
        <div className="w-10 h-1 bg-border-light rounded-full mx-auto mb-5" />

        <div className="flex items-center justify-between mb-4">
          <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">Selected Text</span>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary p-1 -mr-1">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <blockquote className="border-l-2 border-accent pl-3 mb-5">
          <p className="text-text-secondary text-sm leading-relaxed line-clamp-3">"{passage}"</p>
        </blockquote>

        <div className="flex gap-2 mb-5">
          {MODES.map((m) => (
            <button
              key={m.key}
              onClick={() => handleExplain(m.key)}
              className={`flex-1 py-2.5 rounded-xl text-sm font-medium border transition-all duration-150
                ${mode === m.key && result
                  ? 'bg-accent text-white border-accent'
                  : 'bg-surface text-text-secondary border-border hover:border-border-light hover:text-text-primary'
                }`}
            >
              {m.label}
            </button>
          ))}
        </div>

        {loading && (
          <div className="space-y-2 animate-pulse">
            <div className="skeleton w-full h-4" />
            <div className="skeleton w-5/6 h-4" />
            <div className="skeleton w-4/5 h-4" />
          </div>
        )}

        {result && !loading && (
          <div className="animate-fade-up">
            <p className="text-text-primary text-sm leading-relaxed">{result}</p>
          </div>
        )}

        {!result && !loading && (
          <p className="text-text-muted text-sm text-center py-4">Select an option above to get an AI explanation</p>
        )}
      </div>
    </>
  )
}
