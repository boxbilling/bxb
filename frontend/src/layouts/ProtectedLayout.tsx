import { Outlet, useNavigate } from "react-router-dom"
import { Loader2, Lock } from "lucide-react"
import { useAuth } from "@/hooks/useAuth"
import { Button } from "@/components/ui/button"

export default function ProtectedLayout() {
  const { user, isLoading, isAuthenticated } = useAuth()
  const navigate = useNavigate()

  if (isLoading) {
    return (
      <main className="flex-1 container mx-auto px-6 py-8">
        <div className="flex items-center justify-center min-h-[400px]">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      </main>
    )
  }

  if (!isAuthenticated || !user) {
    return (
      <main className="flex-1 container mx-auto px-6 py-8">
        <div className="max-w-md mx-auto text-center py-16">
          <Lock className="w-16 h-16 mx-auto mb-4 text-muted-foreground" />
          <h1 className="text-2xl font-bold text-foreground mb-2">Login Required</h1>
          <p className="text-muted-foreground mb-6">
            Please log in to access this page.
          </p>
          <Button onClick={() => navigate("/login")}>
            Go to Login
          </Button>
        </div>
      </main>
    )
  }

  return <Outlet />
}
