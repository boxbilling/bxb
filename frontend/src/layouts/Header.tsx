import { useState } from "react"
import { Link, useNavigate, useLocation } from "react-router-dom"
import {Menu, X, Plus, Compass, BookOpen} from "lucide-react"
import { Button } from "@/components/ui/button.tsx"
import { config } from "@/lib/config.ts"
import { UserMenu } from "@/components/user-menu.tsx"
import { getSection } from "@/lib/links.ts"

const mainLinks = getSection("Main")?.links || []

export function Header() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const isHomePage = location.pathname === "/"
  const logoLink = isHomePage ? "/explore" : "/"

  return (
    <header className="border-b border-border bg-background/80 backdrop-blur-sm top-0 z-50">
      <div className="w-full px-6 h-14 flex items-center justify-between">
        {/* Left: Mobile menu button */}
        <div className="flex items-center gap-6 sm:flex-1">
          <Button
            variant="ghost"
            size="sm"
            className="sm:hidden"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </Button>

          {/* Desktop: Logo on left */}
          <span className="font-semibold text-foreground">{config.VITE_APP_TITLE}</span>
        </div>

        {/* Center: Logo on mobile */}
        <Link to={logoLink} className="sm:hidden absolute left-1/2 -translate-x-1/2 items-center gap-2 group">
          <span className="font-semibold text-foreground">{config.VITE_APP_TITLE}</span>
        </Link>
      </div>

      {/* Mobile Menu */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t border-border bg-background">
          <nav className="container mx-auto px-6 py-4 flex flex-col gap-2">
            {mainLinks.filter(link => link.path !== "/").map((link) => (
              <Link
                key={link.path}
                to={link.path}
                onClick={() => setMobileMenuOpen(false)}
                className="flex items-center gap-3 px-3 py-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              >
                <link.icon className="w-4 h-4" />
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
      )}
    </header>
  )
}
