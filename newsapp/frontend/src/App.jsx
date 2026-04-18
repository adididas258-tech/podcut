import { Routes, Route } from 'react-router-dom'
import Feed from './pages/Feed'
import Article from './pages/Article'
import Settings from './pages/Settings'
import { ApiKeyProvider } from './components/ApiKeyContext'

export default function App() {
  return (
    <ApiKeyProvider>
      <div className="min-h-screen bg-bg text-text-primary">
        <Routes>
          <Route path="/" element={<Feed />} />
          <Route path="/article/:id" element={<Article />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </div>
    </ApiKeyProvider>
  )
}
