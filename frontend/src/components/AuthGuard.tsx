import { Navigate } from 'react-router-dom'
import { isAuthenticated } from '@/lib/auth'
import type { ReactNode } from 'react'

export default function AuthGuard({ children }: { children: ReactNode }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}
