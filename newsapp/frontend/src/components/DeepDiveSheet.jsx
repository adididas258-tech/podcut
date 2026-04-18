import { useState, useEffect } from 'react'
import { fetchDeepDive } from './api'
import { useApiKey } from './ApiKeyContext'

export default function DeepDiveSheet({ articleId, onClose }) {
  const { apiKey } = useApiKey()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchDeepDive(articleId, apiKey)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [articleId])

  return (
    <>
      <div className="overlay" onClick={onClose} />
      <div className="bottom-sheet px-5 pt-2 pb-8">
        <div className="w-10 h-1 bg-border-light rounded-full mx-auto mb-5" />

        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-accent animate-pulse-soft" />
            <span className="text-xs font-semibold text-accent uppercase tracking-wider">Deep Dive Analysis</span>
          </div>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary p-1 -mr-1">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {loading && <DeepDiveSkeleton />}
        {error && <p className="text-text-secondary text-sm py-4">{error}</p>}

        {data && !loading && (
          <div className="space-y-6 animate-fade-up">
            {data.headline && (
              <h2 className="font-serif font-bold text-2xl text-text-primary leading-tight">{data.headline}</h2>
            )}

            {data.executive_summary && (
              <Section title="Analysis">
                <p className="text-text-secondary leading-relaxed text-sm">{data.executive_summary}</p>
              </Section>
            )}

            {data.context && (
              <Section title="Context">
                <p className="text-text-secondary leading-relaxed text-sm">{data.context}</p>
              </Section>
            )}

            {data.implications?.length > 0 && (
              <Section title="Implications">
                <ul className="space-y-2.5">
                  {data.implications.map((imp, i) => (
                    <li key={i} className="flex gap-3 text-sm text-text-secondary">
                      <span className="text-accent mt-0.5 flex-shrink-0">→</span>
                      <span className="leading-relaxed">{imp}</span>
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            {data.counterpoints && (
              <Section title="Counterpoint">
                <p className="text-text-secondary leading-relaxed text-sm italic">{data.counterpoints}</p>
              </Section>
            )}

            {data.questions_raised?.length > 0 && (
              <Section title="Open Questions">
                <ul className="space-y-2">
                  {data.questions_raised.map((q, i) => (
                    <li key={i} className="text-sm text-text-secondary flex gap-2">
                      <span className="text-text-muted">Q{i + 1}.</span>
                      <span className="leading-relaxed">{q}</span>
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            {data.related_themes?.length > 0 && (
              <Section title="Related Themes">
                <div className="flex flex-wrap gap-2">
                  {data.related_themes.map((theme, i) => (
                    <span key={i} className="tag text-accent border-accent/30 bg-accent/10">{theme}</span>
                  ))}
                </div>
              </Section>
            )}

            {data.reading_list?.length > 0 && (
              <Section title="Further Reading">
                <ul className="space-y-1.5">
                  {data.reading_list.map((item, i) => (
                    <li key={i} className="text-sm text-text-secondary flex gap-2">
                      <span className="text-text-muted">·</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </Section>
            )}
          </div>
        )}
      </div>
    </>
  )
}

function Section({ title, children }) {
  return (
    <div>
      <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2.5">{title}</h3>
      {children}
    </div>
  )
}

function DeepDiveSkeleton() {
  return (
    <div className="space-y-5 animate-pulse">
      <div className="skeleton w-3/4 h-7" />
      <div className="skeleton w-full h-4" />
      <div className="skeleton w-5/6 h-4" />
      <div className="skeleton w-full h-4" />
      <div className="skeleton w-2/3 h-4" />
      <div className="space-y-2 pt-2">
        {[1,2,3].map(i => <div key={i} className="skeleton w-full h-4" />)}
      </div>
    </div>
  )
}
