const TOKEN_KEY = 'bxb_auth_token'

// --- Token storage ---

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

// --- JWT decoding (no validation — server validates) ---

export function parseToken(
  token: string,
): { sub: string; org: string; role: string; exp: number } | null {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return null
    const payload = JSON.parse(atob(parts[1]))
    if (!payload.sub || !payload.org || !payload.role || !payload.exp) return null
    return { sub: payload.sub, org: payload.org, role: payload.role, exp: payload.exp }
  } catch {
    return null
  }
}

export function isTokenExpired(token: string): boolean {
  const parsed = parseToken(token)
  if (!parsed) return true
  return parsed.exp * 1000 < Date.now()
}

// --- Auth state helpers ---

export function isAuthenticated(): boolean {
  const token = getToken()
  if (!token) return false
  return !isTokenExpired(token)
}

export function getCurrentAuth(): {
  userId: string
  orgId: string
  role: string
} | null {
  const token = getToken()
  if (!token) return null
  const parsed = parseToken(token)
  if (!parsed) return null
  if (parsed.exp * 1000 < Date.now()) return null
  return { userId: parsed.sub, orgId: parsed.org, role: parsed.role }
}
