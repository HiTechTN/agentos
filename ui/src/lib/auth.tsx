"use client"

import { createContext, useContext, useState, useCallback, type ReactNode } from "react"

interface User {
  sub: string
  workspace: string
  role: string
}

interface AuthContext {
  user: User | null
  token: string | null
  login: (token: string) => void
  logout: () => void
  isAuthenticated: boolean
}

const AuthCtx = createContext<AuthContext>({
  user: null, token: null, login: () => {}, logout: () => {}, isAuthenticated: false,
})

function decodeToken(token: string): User | null {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]))
    return { sub: payload.sub, workspace: payload.workspace, role: payload.role }
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() =>
    typeof window !== "undefined" ? localStorage.getItem("agentos_token") : null,
  )
  const [user, setUser] = useState<User | null>(() => (token ? decodeToken(token) : null))

  const login = useCallback((t: string) => {
    localStorage.setItem("agentos_token", t)
    setToken(t)
    setUser(decodeToken(t))
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem("agentos_token")
    setToken(null)
    setUser(null)
  }, [])

  return (
    <AuthCtx.Provider value={{ user, token, login, logout, isAuthenticated: !!token }}>
      {children}
    </AuthCtx.Provider>
  )
}

export const useAuth = () => useContext(AuthCtx)
