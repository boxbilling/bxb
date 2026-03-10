import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Spinner } from '@/components/ui/spinner'
import { authApi, setActiveOrganizationId } from '@/lib/api'
import { setToken } from '@/lib/auth'

const loginSchema = z.object({
  email: z.string().email('Please enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
})

type LoginFormValues = z.infer<typeof loginSchema>

type OrgBranding = {
  name: string
  slug: string
  logo_url: string | null
  portal_accent_color: string | null
}

export default function LoginPage() {
  const { slug } = useParams<{ slug?: string }>()
  const navigate = useNavigate()

  const [orgBranding, setOrgBranding] = useState<OrgBranding | null>(null)
  const [orgLoading, setOrgLoading] = useState(!!slug)
  const [orgError, setOrgError] = useState<string | null>(null)
  const [loginError, setLoginError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  })

  useEffect(() => {
    if (!slug) return
    setOrgLoading(true)
    authApi
      .getOrgBySlug(slug)
      .then((org) => {
        setOrgBranding(org)
        setOrgError(null)
      })
      .catch(() => {
        setOrgError('Organization not found')
      })
      .finally(() => setOrgLoading(false))
  }, [slug])

  const onSubmit = async (values: LoginFormValues) => {
    setLoginError(null)
    try {
      const response = await authApi.login({
        email: values.email,
        password: values.password,
        org_slug: slug,
      })
      setToken(response.access_token)
      setActiveOrganizationId(response.organization.id)
      navigate('/admin')
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'An unexpected error occurred'
      setLoginError(message)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          {orgLoading ? (
            <div className="flex justify-center py-4">
              <Spinner className="size-6" />
            </div>
          ) : orgError ? (
            <CardTitle className="text-destructive">{orgError}</CardTitle>
          ) : (
            <>
              {orgBranding?.logo_url && (
                <img
                  src={orgBranding.logo_url}
                  alt={orgBranding.name}
                  className="mx-auto mb-4 h-12 w-auto"
                />
              )}
              <CardTitle>
                {orgBranding
                  ? `Sign in to ${orgBranding.name}`
                  : 'Sign in to BoxBilling'}
              </CardTitle>
            </>
          )}
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                {...register('email')}
              />
              {errors.email && (
                <p className="text-sm text-destructive">
                  {errors.email.message}
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                {...register('password')}
              />
              {errors.password && (
                <p className="text-sm text-destructive">
                  {errors.password.message}
                </p>
              )}
            </div>
            {loginError && (
              <p className="text-sm text-destructive">{loginError}</p>
            )}
            <Button
              type="submit"
              className="w-full"
              disabled={isSubmitting || !!orgError}
            >
              {isSubmitting ? <Spinner className="mr-2 size-4" /> : null}
              Sign in
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
