import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { fetchArticle } from '../components/api'
import { useApiKey } from '../components/ApiKeyContext'
import DeepDiveSheet from '../components/DeepDiveSheet'
import ExplainSheet from '../components/ExplainSheet'

const SENTIMENT_CLASS = {
  Positive: 'sentiment-positive',
  Negative: 'sentiment-negative',
  Neutral: 'sentiment-neutral',
  Mixed: 'sentiment-mixed',
}

export default function Article() {
  const { id } = useParams()
  const { apiKey } = useApiKey()
  const navigate = useNavigate()
  const [article, setArticle] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showDeepDive, setShowDeepDive] = useState(false)
  const [explainData, setExplainData] = useState(null)
  const [readProgress, setReadProgress] = useState(0)
  const contentRef = useRef(null)

  useEffect(() => {
    fetchArticle(id, apiKey)
      .then(setArticle)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  useEffect(() => {
    const onScroll = () => {
      const el = contentRef.current
      if (!el) return
      const { top, height } = el.getBoundingClientRect()
      const windowHeight = window.innerHeight
      const progress = Math.min(100, Math.max(0, ((windowHeight - top) / height) * 100))
      setReadProgress(progress)
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const handleTextSelect = () => {
    const selection = window.getSelection()
    const text = selection?.toString().trim()
    if (text && text.length > 20) {
      setExplainData({ passage: text, articleTitle: article?.title || '' })
    }
  }

  if (loading) return <ArticleSkeleton onBack={() => navigate(-1)} />
  if (error) return (
    <div className="min-h-screen bg-bg flex flex-col items-center justify-center p-8">
      <p className="text-text-secondary text-sm mb-4">{error}</p>
      <button onClick={() => navigate(-1)} className="text-accent text-sm">Go back</button>
    </div>
  )
  if (!article) return null

  const ai = article.ai_analysis

  return (
    <div className="min-h-screen bg-bg">
      {/* Progress bar */}
      <div className="fixed top-0 left-0 right-0 h-0.5 bg-border z-50">
        <div
          className="h-full bg-accent transition-all duration-150"
          style={{ width: `${readProgress}%` }}
        />
      </div>

      {/* Header */}
      <header className="sticky top-0 z-30 bg-bg/95 backdrop-blur-sm border-b border-border safe-top">
        <div className="flex items-center gap-3 px-4 py-3">
          <button onClick={() => navigate(-1)} className="p-1 -ml-1 text-text-secondary hover:text-text-primary transition-colors">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <span className="text-text-muted text-sm flex-1 truncate">{article.source}</span>
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1 -mr-1 text-text-muted hover:text-text-primary transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </a>
        </div>
      </header>

      {/* Article Image */}
      {article.image && (
        <div className="h-56 overflow-hidden bg-surface">
          <img src={article.image} alt="" className="w-full h-full object-cover opacity-70" />
        </div>
      )}

      {/* Content */}
      <div ref={contentRef} className="px-4 pt-5 pb-32" onMouseUp={handleTextSelect} onTouchEnd={handleTextSelect}>
        {/* Meta */}
        <div className="flex items-center gap-2 mb-3">
          <span className="text-text-muted text-xs">{article.source}</span>
          <span className="text-text-muted text-xs">·</span>
          <span className="text-text-muted text-xs">{article.read_time} min read</span>
          {ai?.sentiment && (
            <>
              <span className="text-text-muted text-xs">·</span>
              <span className={`tag ${SENTIMENT_CLASS[ai.sentiment] || 'sentiment-neutral'}`}>{ai.sentiment}</span>
            </>
          )}
        </div>

        {/* Title */}
        <h1 className="font-serif font-bold text-2xl text-text-primary leading-tight mb-4">{article.title}</h1>

        {/* Tags */}
        {ai?.tags?.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-5">
            {ai.tags.map((tag, i) => (
              <span key={i} className="tag text-text-secondary border-border">{tag}</span>
            ))}
          </div>
        )}

        {/* AI Analysis Block */}
        {ai && (
          <div className="bg-surface border border-border rounded-2xl p-4 mb-6">
            <div className="flex items-center gap-2 mb-3">
              <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse-soft" />
              <span className="text-xs font-semibold text-accent uppercase tracking-wider">AI Analysis</span>
            </div>

            {ai.analysis && (
              <p className="text-text-secondary text-sm leading-relaxed mb-4">{ai.analysis}</p>
            )}

            {ai.key_points?.length > 0 && (
              <ul className="space-y-2 mb-4">
                {ai.key_points.map((point, i) => (
                  <li key={i} className="flex gap-2 text-sm text-text-secondary">
                    <span className="text-accent flex-shrink-0 mt-0.5">·</span>
                    <span className="leading-relaxed">{point}</span>
                  </li>
                ))}
              </ul>
            )}

            {ai.significance && (
              <p className="text-text-muted text-xs leading-relaxed border-t border-border pt-3">{ai.significance}</p>
            )}
          </div>
        )}

        {/* Article Body */}
        {article.full_content ? (
          <div className="prose-custom">
            {article.full_content.split('\n').filter(Boolean).map((para, i) => (
              <p key={i} className="text-text-secondary text-base leading-relaxed mb-4">{para}</p>
            ))}
          </div>
        ) : (
          <p className="text-text-secondary text-base leading-relaxed">{article.summary}</p>
        )}

        {/* Select-to-explain hint */}
        <div className="mt-6 p-3 bg-surface border border-border rounded-xl">
          <p className="text-text-muted text-xs text-center">
            Select any text to get AI explanations, simplifications, or deeper context
          </p>
        </div>
      </div>

      {/* Bottom Action Bar */}
      <div className="fixed bottom-0 left-0 right-0 z-30 bg-bg/95 backdrop-blur-sm border-t border-border safe-bottom">
        <div className="flex items-center gap-3 px-4 py-3">
          <button
            onClick={() => setShowDeepDive(true)}
            className="flex-1 flex items-center justify-center gap-2 py-3 bg-accent rounded-xl text-white font-semibold text-sm transition-opacity active:opacity-80"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            Deep Dive
          </button>
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-2 px-5 py-3 bg-surface border border-border rounded-xl text-text-secondary font-medium text-sm"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
            Source
          </a>
        </div>
      </div>

      {/* Sheets */}
      {showDeepDive && (
        <DeepDiveSheet articleId={id} onClose={() => setShowDeepDive(false)} />
      )}
      {explainData && (
        <ExplainSheet
          passage={explainData.passage}
          articleTitle={explainData.articleTitle}
          onClose={() => setExplainData(null)}
        />
      )}
    </div>
  )
}

function ArticleSkeleton({ onBack }) {
  return (
    <div className="min-h-screen bg-bg">
      <header className="sticky top-0 z-30 bg-bg border-b border-border safe-top">
        <div className="flex items-center gap-3 px-4 py-3">
          <button onClick={onBack} className="p-1 -ml-1 text-text-secondary">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div className="skeleton flex-1 h-4" />
        </div>
      </header>
      <div className="px-4 pt-5 space-y-4 animate-pulse">
        <div className="skeleton w-full h-7" />
        <div className="skeleton w-4/5 h-7" />
        <div className="skeleton w-full h-32 rounded-2xl" />
        {[1,2,3,4,5].map(i => <div key={i} className="skeleton w-full h-4" />)}
      </div>
    </div>
  )
}
