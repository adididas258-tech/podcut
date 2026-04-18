const BASE = '/api'

function headers(apiKey) {
  return apiKey ? { 'X-API-Key': apiKey, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' }
}

export async function fetchFeed(category = 'All', refresh = false, apiKey = '') {
  const params = new URLSearchParams({ category })
  if (refresh) params.set('refresh', 'true')
  const res = await fetch(`${BASE}/feed?${params}`, { headers: headers(apiKey) })
  if (!res.ok) throw new Error('Failed to fetch feed')
  return res.json()
}

export async function fetchArticle(id, apiKey = '') {
  const res = await fetch(`${BASE}/article/${id}`, { headers: headers(apiKey) })
  if (!res.ok) throw new Error('Failed to fetch article')
  return res.json()
}

export async function fetchDeepDive(id, apiKey = '') {
  const res = await fetch(`${BASE}/deep-dive/${id}`, { headers: headers(apiKey) })
  if (!res.ok) throw new Error('Failed to fetch deep dive')
  return res.json()
}

export async function fetchExplanation(passage, articleTitle, mode, apiKey = '') {
  const res = await fetch(`${BASE}/explain`, {
    method: 'POST',
    headers: headers(apiKey),
    body: JSON.stringify({ passage, article_title: articleTitle, mode }),
  })
  if (!res.ok) throw new Error('Failed to explain')
  return res.json()
}

export async function fetchCategories(apiKey = '') {
  const res = await fetch(`${BASE}/categories`, { headers: headers(apiKey) })
  if (!res.ok) throw new Error('Failed to fetch categories')
  return res.json()
}
