import {
  Github,
  LayoutDashboard,
  Linkedin,
  Package,
  Twitter,
} from "lucide-react"
import { config } from "@/lib/config"

export interface NavLink {
  label: string
  path: string
  icon: typeof LayoutDashboard
}

export interface NavSection {
  title: string
  links: NavLink[]
}

export const sections: NavSection[] = [
  {
    title: "Main",
    links: [
      { path: "/", label: "Home", icon: LayoutDashboard },
      { path: "/items", label: "Items", icon: Package },
    ],
  },
  {
    title: "Social",
    links: [
      { label: "Github", path: config.VITE_GITHUB_URL, icon: Github },
      {
        label: "Twitter",
        path: "https://twitter.com/intent/tweet?url="+config.VITE_APP_URL,
        icon: Twitter,
      },
      {
        label: "Linkedin",
        path: "https://www.linkedin.com/sharing/share-offsite/?url="+config.VITE_APP_URL,
        icon: Linkedin,
      },
    ],
  },
]

export function getSection(name: string): NavSection | undefined {
  return sections.find((section) => section.title === name)
}
