import { useNavigate } from "react-router-dom"
import { Helmet } from "react-helmet-async"
import { config } from "@/lib/config.ts"
import { useAuth } from "@/hooks/useAuth"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { User, Mail, AtSign, LogOut, Loader2 } from "lucide-react"

export default function UserProfilePage() {
  const { user, isLoading, isAuthenticated, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate("/")
  }

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
          <User className="w-16 h-16 mx-auto mb-4 text-muted-foreground" />
          <h1 className="text-2xl font-bold text-foreground mb-2">Not Logged In</h1>
          <p className="text-muted-foreground mb-6">
            Please log in to view your profile.
          </p>
          <Button onClick={() => navigate("/login")}>
            Go to Login
          </Button>
        </div>
      </main>
    )
  }

  const initials = user.name
    ? user.name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2)
    : (user.email?.[0]?.toUpperCase() ?? "U")

  return (
    <>
      <Helmet>
        <title>{`Profile | ${config.VITE_APP_TITLE}`}</title>
        <meta name="description" content="View and manage your SchemaHub profile settings." />
        <link rel="canonical" href={`${config.VITE_APP_URL}/profile`} />
        <meta property="og:title" content={`Profile | ${config.VITE_APP_TITLE}`} />
        <meta property="og:description" content="View and manage your SchemaHub profile settings." />
        <meta property="og:url" content={`${config.VITE_APP_URL}/profile`} />
        <meta property="og:type" content="website" />
        <meta name="twitter:title" content={`Profile | ${config.VITE_APP_TITLE}`} />
        <meta name="twitter:description" content="View and manage your SchemaHub profile settings." />
      </Helmet>
      <main className="flex-1 container mx-auto px-6 py-8">
        <div className="max-w-2xl mx-auto">
          <h1 className="text-3xl font-bold text-foreground mb-8">Profile</h1>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-4">
              <Avatar className="w-16 h-16">
                <AvatarImage src={user.picture ?? undefined} alt={user.name ?? user.email} />
                <AvatarFallback className="text-lg">{initials}</AvatarFallback>
              </Avatar>
              <div>
                <CardTitle className="text-xl">
                  {user.name ?? "User"}
                </CardTitle>
                <p className="text-sm text-muted-foreground">
                  Account Details
                </p>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/50">
              <Mail className="w-5 h-5 text-muted-foreground" />
              <div>
                <p className="text-xs text-muted-foreground">Email</p>
                <p className="text-sm font-medium text-foreground">{user.email}</p>
              </div>
            </div>

            {user.username && (
              <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/50">
                <AtSign className="w-5 h-5 text-muted-foreground" />
                <div>
                  <p className="text-xs text-muted-foreground">Username</p>
                  <p className="text-sm font-medium text-foreground">{user.username}</p>
                </div>
              </div>
            )}

            {user.name && (
              <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/50">
                <User className="w-5 h-5 text-muted-foreground" />
                <div>
                  <p className="text-xs text-muted-foreground">Name</p>
                  <p className="text-sm font-medium text-foreground">{user.name}</p>
                </div>
              </div>
            )}

            <div className="pt-4 border-t border-border">
              <Button
                variant="outline"
                className="w-full text-destructive hover:text-destructive hover:bg-destructive/10"
                onClick={handleLogout}
              >
                <LogOut className="w-4 h-4 mr-2" />
                Log Out
              </Button>
            </div>
          </CardContent>
        </Card>
        </div>
      </main>
    </>
  )
}
