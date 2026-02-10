import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { Helmet } from "react-helmet-async"
import { GoogleLogin, GoogleOAuthProvider } from "@react-oauth/google"
import { AlertCircle, Loader2 } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useAuth } from "@/hooks/useAuth"
import client from "@/lib/api"
import { config } from "@/lib/config"

interface GoogleAuthResponse {
  access_token: string
  token_type: string
  user: {
    email: string
    username?: string | null
    name?: string | null
    picture?: string | null
  }
}

function LoginContent() {
  const navigate = useNavigate()
  const { login } = useAuth()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const clientId = config.VITE_GOOGLE_CLIENT_ID
  const hasClientId = clientId && clientId.trim() !== ""

  const handleGoogleSuccess = async (credentialResponse: { credential?: string }) => {
    if (!credentialResponse.credential) {
      setError("No credential received from Google")
      return
    }

    setIsLoading(true)
    setError(null)

    // @ts-expect-error endpoint not yet in backend schema
    const { data, error: apiError } = await client.POST("/auth/google", {
      body: { credential: credentialResponse.credential },
    })

    if (apiError || !data) {
      const errorMessage = typeof apiError === "object" && apiError && "message" in apiError ? (apiError as any).message : "Login failed"
      setError(errorMessage)
      setIsLoading(false)
      return
    }

    const authData = data as unknown as GoogleAuthResponse
    login(authData.access_token, authData.user)
    navigate("/")
  }

  const handleGoogleError = () => {
    setError("Google login failed. Please try again.")
  }

  return (
    <>
      <Helmet>
        <title>{`Login | ${config.VITE_APP_TITLE}`}</title>
        <meta name="description" content="Sign in to SchemaHub to create, edit, and manage your database schemas." />
        <link rel="canonical" href={`${config.VITE_APP_URL}/login`} />
        <meta property="og:title" content={`Login | ${config.VITE_APP_TITLE}`} />
        <meta property="og:description" content="Sign in to SchemaHub to create, edit, and manage your database schemas." />
        <meta property="og:url" content={`${config.VITE_APP_URL}/login`} />
        <meta property="og:type" content="website" />
        <meta name="twitter:title" content={`Login | ${config.VITE_APP_TITLE}`} />
        <meta name="twitter:description" content="Sign in to SchemaHub to create, edit, and manage your database schemas." />
      </Helmet>
      <div className="min-h-screen flex items-center justify-center bg-secondary/5 relative overflow-hidden">
        <Card className="max-w-md w-full mx-4 relative z-10">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl">{config.VITE_APP_TITLE}</CardTitle>
            <CardDescription>{config.VITE_APP_SLOGAN}</CardDescription>
          </CardHeader>

          <CardContent className="space-y-4">
            {error && (
              <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-lg">
                <div className="flex items-center gap-2 text-sm text-destructive">
                  <AlertCircle size={16} />
                  <span>{error}</span>
                </div>
              </div>
            )}

            {!hasClientId ? (
              <div className="p-4 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                <div className="flex items-start gap-3">
                  <AlertCircle className="text-amber-500 flex-shrink-0 mt-0.5" size={20} />
                  <div className="text-sm text-amber-200">
                    <p className="font-semibold mb-1">Google OAuth Not Configured</p>
                    <p className="text-xs mb-2 text-amber-300/80">
                      To enable login, set up Google OAuth credentials:
                    </p>
                    <ol className="text-xs list-decimal list-inside space-y-1 text-amber-300/80">
                      <li>Create OAuth 2.0 credentials in Google Cloud Console</li>
                      <li>Add VITE_GOOGLE_CLIENT_ID to your .env file</li>
                      <li>Restart the development server</li>
                    </ol>
                  </div>
                </div>
              </div>
            ) : isLoading ? (
              <div className="flex justify-center py-4">
                <Loader2 className="animate-spin text-muted-foreground" size={32} />
              </div>
            ) : (
              <div className="w-full flex justify-center">
                <GoogleLogin
                  onSuccess={handleGoogleSuccess}
                  onError={handleGoogleError}
                  width="350"
                  size="large"
                  text="signin_with"
                  shape="rectangular"
                  theme="filled_black"
                />
              </div>
            )}

            <div className="text-center text-xs text-muted-foreground pt-4 space-y-2">
              <p>Login with GitHub coming soon</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  )
}

export default function LoginPage() {
  const clientId = config.VITE_GOOGLE_CLIENT_ID

  if (!clientId || clientId.trim() === "") {
    return <LoginContent />
  }

  return (
    <GoogleOAuthProvider clientId={clientId}>
      <LoginContent />
    </GoogleOAuthProvider>
  )
}
