import { Link } from "react-router-dom"
import { config } from "@/lib/config.ts"
import { getSection } from "@/lib/links.ts"

export function Footer() {
  return (
    <footer className="mt-auto">
      <div className="border-t border-white/10">
        <div className="container mx-auto px-4 py-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-foreground/90">
                {config.VITE_APP_TITLE}{" "}
              </span>
            </div>

            <p className="text-sm text-muted-foreground text-center">
              {config.VITE_APP_SLOGAN}
            </p>

            <div className="flex items-center gap-4">
              {getSection("Social")?.links.map((link) => (
                <a
                  key={link.path}
                  href={link.path}
                  target="_blank"
                  rel="noreferrer"
                  className="text-muted-foreground hover:text-emerald-400 transition-colors"
                >
                  <link.icon className="h-5 w-5" />
                </a>
              ))}
            </div>
          </div>

          <div className="mt-6 pt-6 border-t border-white/5 flex flex-col md:flex-row items-center justify-between gap-2 text-xs text-muted-foreground">
            <p>
              &copy; {new Date().getFullYear()} {config.VITE_APP_TITLE}. All
              rights reserved.
            </p>
            <div className="flex items-center gap-4">
              {getSection("Main")?.links.map((link) => (
                <Link
                  key={link.path}
                  to={link.path}
                  className="hover:text-foreground transition-colors"
                >
                  {link.label}
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>
    </footer>
  )
}
