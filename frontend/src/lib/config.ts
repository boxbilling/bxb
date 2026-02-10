export interface Config {
  VITE_APP_TITLE: string
  VITE_APP_SLOGAN: string
  VITE_APP_EMAIL: string
  VITE_APP_URL: string
  VITE_API_URL: string
  VITE_GITHUB_URL: string
  VITE_GOOGLE_CLIENT_ID: string
}

export const config: Config = {
  VITE_APP_TITLE: import.meta.env.VITE_APP_TITLE || "Fordnox",
  VITE_APP_SLOGAN: import.meta.env.VITE_APP_SLOGAN || "AI template",
  VITE_APP_EMAIL: import.meta.env.VITE_APP_EMAIL || "fordnox@gmail.com",
  VITE_APP_URL: import.meta.env.VITE_APP_URL || "https://example.com",
  VITE_API_URL: import.meta.env.VITE_API_URL || "http://localhost:8000",
  VITE_GITHUB_URL: import.meta.env.VITE_GITHUB_URL || "https://github.com/fordnox/mle-template",
  VITE_GOOGLE_CLIENT_ID: import.meta.env.VITE_GOOGLE_CLIENT_ID || "",
}
