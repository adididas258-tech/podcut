import { useEffect, useRef } from 'react'

export default function CategoryFilter({ categories, active, onChange }) {
  const scrollRef = useRef(null)

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const activeEl = el.querySelector('[data-active="true"]')
    if (activeEl) activeEl.scrollIntoView({ inline: 'center', behavior: 'smooth', block: 'nearest' })
  }, [active])

  return (
    <div
      ref={scrollRef}
      className="flex gap-2 overflow-x-auto py-3 scrollbar-hide"
      style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
    >
      {categories.map((cat) => (
        <button
          key={cat}
          data-active={cat === active}
          onClick={() => onChange(cat)}
          className={`flex-shrink-0 px-4 py-1.5 rounded-full text-sm font-medium transition-all duration-200 border
            ${cat === active
              ? 'bg-accent text-white border-accent'
              : 'bg-transparent text-text-secondary border-border hover:border-border-light hover:text-text-primary'
            }`}
        >
          {cat}
        </button>
      ))}
    </div>
  )
}
