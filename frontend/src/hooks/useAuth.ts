import { useState, useCallback, useMemo } from "react"

interface User {
  email: string
  username?: string | null
  name?: string | null
  picture?: string | null
}

export function useAuth() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("token"))
  const [user, setUser] = useState<User | null>(() => {
    const stored = localStorage.getItem("user")
    return stored ? JSON.parse(stored) : null
  })
  const [isLoading] = useState(false)

  const isAuthenticated = !!token && !!user

  const login = useCallback((accessToken: string, userData: User) => {
    localStorage.setItem("token", accessToken)
    localStorage.setItem("user", JSON.stringify(userData))
    setToken(accessToken)
    setUser(userData)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem("token")
    localStorage.removeItem("user")
    setToken(null)
    setUser(null)
  }, [])

  return useMemo(
    () => ({ user, token, isLoading, isAuthenticated, login, logout }),
    [user, token, isLoading, isAuthenticated, login, logout],
  )
}
