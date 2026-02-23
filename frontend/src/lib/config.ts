export interface Config {
  VITE_APP_TITLE: string
  VITE_APP_SLOGAN: string
  VITE_APP_EMAIL: string
  VITE_APP_URL: string
  VITE_API_URL: string
  VITE_GITHUB_URL: string
}

export const config: Config = {
  VITE_APP_TITLE: import.meta.env.VITE_APP_TITLE || "BxB",
  VITE_APP_SLOGAN: import.meta.env.VITE_APP_SLOGAN || "BoxBilling",
  VITE_APP_EMAIL: import.meta.env.VITE_APP_EMAIL || "info@boxbilling.com",
  VITE_APP_URL: import.meta.env.VITE_APP_URL || "http://localhost:3000",
  VITE_API_URL: import.meta.env.VITE_API_URL || "http://localhost:8000",
  VITE_GITHUB_URL: import.meta.env.VITE_GITHUB_URL || "https://github.com/boxbilling",
}
