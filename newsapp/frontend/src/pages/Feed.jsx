import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import NewsCard, { NewsCardSkeleton } from '../components/NewsCard'
import CategoryFilter from '../components/CategoryFilter'
import { fetchFeed, fetchCategories } from '../components/api'
import { useApiKey } from '../components/ApiKeyContext'

export default function Feed() {
  const { apiKey } = useApiKey()
  const navigate = useNavigate()
  const [articles, setArticles] = useState([])
  const [categories, setCategories] = useState(['All'])
  const [activeCategory, setActiveCategory] = useState('All')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)

  const load = useCallback(async (category = activeCategory, refresh = false) => {
    if (refresh) setRefreshing(true)
    else setLoading(true)
    setError(null)
    try {
      const [feedData, catData] = await Promise.all([
        fetchFeed(category, refresh, apiKey),
        fetchCategories(apiKey),
      ])
      setArticles(feedData.articles)
      setCategories(catData.categories)
    } catch (e) {
      setError('Could not load news. Make sure the backend is running.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [activeCategory, apiKey])

  useEffect(() => { load() }, [])

  const handleCategory = (cat) => {
    setActiveCategory(cat)
    load(cat, false)
  }

  const featured = articles[0]
  const rest = articles.slice(1)

  return (
    <div className="flex flex-col min-h-screen bg-bg">
      {/* Header */}
      <header className="sticky top-0 z-30 bg-bg/95 backdrop-blur-sm border-b border-border safe-top">
        <div className="px-4 pt-4 pb-0">
          <div className="flex items-center justify-between mb-1">
            <div>
              <p className="text-text-muted text-xs font-medium uppercase tracking-widest">
                {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
              </p>
              <h1 className="font-serif font-bold text-2xl text-text-primary leading-none mt-0.5">Pulse</h1>
            </div>
            <div className="flex items-center gap-2">
              {refreshing && (
                <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
              )}
              <button
                onClick={() => load(activeCategory, true)}
                className="p-2 text-text-muted hover:text-text-primary transition-colors"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </button>
              <button
                onClick={() => navigate('/settings')}
                className="p-2 text-text-muted hover:text-text-primary transition-colors"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </button>
            </div>
          </div>

          <CategoryFilter categories={categories} active={activeCategory} onChange={handleCategory} />
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 px-4 pb-8">
        {error && (
          <div className="mt-8 p-4 bg-surface border border-border rounded-xl text-center">
            <p className="text-text-secondary text-sm">{error}</p>
            <button onClick={() => load()} className="mt-3 text-accent text-sm font-medium">Try Again</button>
          </div>
        )}

        {loading && (
          <div>
            {[1, 2, 3, 4, 5].map((i) => <NewsCardSkeleton key={i} />)}
          </div>
        )}

        {!loading && !error && articles.length === 0 && (
          <div className="mt-16 text-center">
            <p className="text-text-secondary text-sm">No articles found for this category.</p>
          </div>
        )}

        {!loading && !error && featured && (
          <div>
            <NewsCard article={featured} featured />
            <div className="h-px bg-border my-1" />
            {rest.map((article) => (
              <NewsCard key={article.id} article={article} />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
