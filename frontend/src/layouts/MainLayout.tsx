import { Outlet } from "react-router-dom"
import { Header } from "@/layouts/Header.tsx"
import { Footer } from "@/layouts/Footer.tsx"

export default function MainLayout() {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Header />
      <Outlet />
      <Footer />
    </div>
  )
}
