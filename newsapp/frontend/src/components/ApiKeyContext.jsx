import { createContext, useContext, useState } from 'react'

const ApiKeyContext = createContext(null)

export function ApiKeyProvider({ children }) {
  const [apiKey, setApiKey] = useState(() => localStorage.getItem('pulse_api_key') || '')

  const saveKey = (key) => {
    localStorage.setItem('pulse_api_key', key)
    setApiKey(key)
  }

  return (
    <ApiKeyContext.Provider value={{ apiKey, saveKey }}>
      {children}
    </ApiKeyContext.Provider>
  )
}

export const useApiKey = () => useContext(ApiKeyContext)
