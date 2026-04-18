import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApiKey } from '../components/ApiKeyContext'

export default function Settings() {
  const navigate = useNavigate()
  const { apiKey, saveKey } = useApiKey()
  const [inputKey, setInputKey] = useState(apiKey)
  const [saved, setSaved] = useState(false)

  const handleSave = () => {
    saveKey(inputKey.trim())
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="min-h-screen bg-bg">
      <header className="sticky top-0 z-30 bg-bg border-b border-border safe-top">
        <div className="flex items-center gap-3 px-4 py-3">
          <button onClick={() => navigate(-1)} className="p-1 -ml-1 text-text-secondary hover:text-text-primary">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <h1 className="font-semibold text-text-primary">Settings</h1>
        </div>
      </header>

      <div className="px-4 py-6 space-y-6">
        <div className="bg-surface border border-border rounded-2xl p-5">
          <h2 className="font-semibold text-text-primary mb-1">Anthropic API Key</h2>
          <p className="text-text-muted text-xs mb-4 leading-relaxed">
            Required for AI analysis, deep dives, and text explanations. Your key is stored locally and never sent to any external server.
          </p>
          <input
            type="password"
            value={inputKey}
            onChange={(e) => setInputKey(e.target.value)}
            placeholder="sk-ant-..."
            className="w-full bg-bg border border-border rounded-xl px-4 py-3 text-text-primary text-sm placeholder:text-text-muted focus:outline-none focus:border-accent transition-colors"
          />
          <button
            onClick={handleSave}
            className={`mt-3 w-full py-3 rounded-xl font-semibold text-sm transition-all
              ${saved ? 'bg-positive/20 text-positive border border-positive/30' : 'bg-accent text-white active:opacity-80'}`}
          >
            {saved ? '✓ Saved' : 'Save Key'}
          </button>
        </div>

        <div className="bg-surface border border-border rounded-2xl p-5">
          <h2 className="font-semibold text-text-primary mb-3">About Pulse</h2>
          <div className="space-y-3 text-sm text-text-secondary">
            <p className="leading-relaxed">
              Pulse is an AI-powered news reader that curates stories from top tech and AI sources, then uses Claude to provide in-depth analysis.
            </p>
            <div className="space-y-1.5 text-xs text-text-muted">
              <p>· Select any text while reading for instant AI explanations</p>
              <p>· Tap "Deep Dive" for extended analysis and implications</p>
              <p>· Pull to refresh for the latest stories</p>
            </div>
          </div>
        </div>

        <div className="bg-surface border border-border rounded-2xl p-5">
          <h2 className="font-semibold text-text-primary mb-3">News Sources</h2>
          <div className="grid grid-cols-2 gap-2 text-xs text-text-secondary">
            {['Hacker News', 'The Verge', 'Wired', 'Ars Technica', 'MIT Tech Review', 'VentureBeat AI', 'TechCrunch', 'Reuters Tech'].map(s => (
              <div key={s} className="flex items-center gap-1.5">
                <span className="w-1 h-1 rounded-full bg-accent" />
                {s}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
