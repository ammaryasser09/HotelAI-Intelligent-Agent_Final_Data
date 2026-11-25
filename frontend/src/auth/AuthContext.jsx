import { createContext, useContext, useEffect, useState } from 'react'
import { api, getToken, setToken } from '../api/client.js'

const AuthContext = createContext(null)

export const homeFor = (role) => (role === 'Admin' ? '/admin' : role === 'Staff' ? '/staff' : '/guest')

export function AuthProvider({ children }) {
  const [account, setAccount] = useState(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (!getToken()) { setReady(true); return }
    api('/auth/me')
      .then(setAccount)
      .catch(() => setToken(null))
      .finally(() => setReady(true))
  }, [])

  async function login(email, password) {
    const res = await api('/auth/login', { method: 'POST', body: { email, password } })
    setToken(res.access_token)
    setAccount(res.account)
    return res.account
  }

  function startSession(res) {
    setToken(res.access_token)
    setAccount(res.account)
    return res.account
  }

  function logout() {
    setToken(null)
    setAccount(null)
  }

  return <AuthContext.Provider value={{ account, ready, login, logout, startSession }}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
