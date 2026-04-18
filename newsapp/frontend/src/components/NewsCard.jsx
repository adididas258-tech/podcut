import { useNavigate } from 'react-router-dom'

const CATEGORY_COLORS = {
  AI: 'text-purple-400 border-purple-400/30 bg-purple-400/10',
  Tech: 'text-blue-400 border-blue-400/30 bg-blue-400/10',
  Business: 'text-amber-400 border-amber-400/30 bg-amber-400/10',
  Science: 'text-emerald-400 border-emerald-400/30 bg-emerald-400/10',
  Security: 'text-red-400 border-red-400/30 bg-red-400/10',
  General: 'text-text-secondary border-border bg-border',
}

function timeAgo(iso) {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

export default function NewsCard({ article, featured = false }) {
  const navigate = useNavigate()
  const catColor = CATEGORY_COLORS[article.category] || CATEGORY_COLORS.General

  return (
    <article
      className={`card-press cursor-pointer border-b border-border last:border-b-0 ${featured ? 'pb-5 pt-2' : 'py-4'}`}
      onClick={() => navigate(`/article/${article.id}`)}
    >
      {featured && article.image && (
        <div className="mb-4 -mx-4 overflow-hidden h-52 bg-surface">
          <img
            src={article.image}
            alt=""
            className="w-full h-full object-cover opacity-80"
            onError={(e) => { e.target.parentElement.style.display = 'none' }}
          />
        </div>
      )}

      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <span className={`tag ${catColor}`}>{article.category}</span>
            <span className="text-text-muted text-xs">{article.source}</span>
            <span className="text-text-muted text-xs">·</span>
            <span className="text-text-muted text-xs">{timeAgo(article.published_at)}</span>
          </div>

          <h2 className={`font-serif font-bold text-text-primary leading-snug ${featured ? 'text-2xl mb-2' : 'text-base mb-1.5'}`}>
            {article.title}
          </h2>

          {article.summary && (
            <p className={`text-text-secondary leading-relaxed ${featured ? 'text-sm line-clamp-3' : 'text-sm line-clamp-2'}`}>
              {article.summary}
            </p>
          )}

          <div className="flex items-center gap-3 mt-2.5">
            <span className="text-text-muted text-xs">{article.read_time} min read</span>
            <span className="flex items-center gap-1 text-accent text-xs font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse-soft inline-block" />
              AI Analysis
            </span>
          </div>
        </div>

        {!featured && article.image && (
          <div className="w-20 h-20 flex-shrink-0 rounded-lg overflow-hidden bg-surface">
            <img
              src={article.image}
              alt=""
              className="w-full h-full object-cover opacity-80"
              onError={(e) => { e.target.parentElement.style.display = 'none' }}
            />
          </div>
        )}
      </div>
    </article>
  )
}

export function NewsCardSkeleton() {
  return (
    <div className="py-4 border-b border-border">
      <div className="flex items-center gap-2 mb-3">
        <div className="skeleton w-14 h-4" />
        <div className="skeleton w-20 h-4" />
      </div>
      <div className="skeleton w-full h-5 mb-2" />
      <div className="skeleton w-4/5 h-5 mb-3" />
      <div className="skeleton w-2/3 h-4 mb-1" />
      <div className="skeleton w-1/2 h-4" />
    </div>
  )
}
