import createClient, { Middleware } from "openapi-fetch"
import type { paths } from "@/lib/schema"
import { config } from "@/lib/config"
import { toast } from "sonner"

const myMiddleware: Middleware = {
  async onRequest({ request }) {
    const token = localStorage.getItem("token")
    if (token) {
      request.headers.set("Authorization", `Bearer ${token}`)
    }
    return request
  },
  async onResponse({ response }) {
    if (!response.ok && response.status !== 401) {
      const errorData = await response.clone().json().catch(() => null)
      const message =
        errorData?.detail || errorData?.message || `Error ${response.status}: ${response.statusText}`

      toast.error("Request failed", {
        description: message,
      })
    }

    return response
  },
  async onError({ error }) {
    console.error("Network error:", error)
    const message = error instanceof Error ? error.message : "Network error occurred"
    toast.error("Connection failed", {
      description: message,
    })
    return undefined
  },
}

const client = createClient<paths>({ baseUrl: config.VITE_API_URL })
client.use(myMiddleware)

export default client
