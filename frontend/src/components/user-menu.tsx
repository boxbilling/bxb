import { Link } from "react-router-dom"
import { LogIn, LogOut, User, Database, MessageSquare, Plug } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { FeedbackDialog } from "@/components/feedback-dialog"
import { useAuth } from "@/hooks/useAuth"

function getInitials(name?: string | null, email?: string) {
  if (name) {
    return name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2)
  }
  return email?.charAt(0).toUpperCase() ?? "U"
}

export function UserMenu() {
  const { user, isAuthenticated, isLoading, logout } = useAuth()

  if (isLoading) {
    return <div className="w-8 h-8 rounded-full bg-muted animate-pulse" />
  }

  if (!isAuthenticated || !user) {
    return (
      <Link to="/login">
        <Button variant="outline" size="sm" className="gap-2">
          <LogIn className="w-4 h-4" />
          Login
        </Button>
      </Link>
    )
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="rounded-full">
          <Avatar className="w-8 h-8">
            <AvatarImage src={user.picture ?? undefined} alt={user.name ?? user.email} />
            <AvatarFallback className="bg-primary/10 text-primary text-xs">
              {getInitials(user.name, user.email)}
            </AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <div className="px-2 py-1.5">
          <p className="text-sm font-medium text-foreground">{user.name ?? user.username}</p>
          <p className="text-xs text-muted-foreground">{user.email}</p>
        </div>
        <DropdownMenuSeparator />
        {user.username && (
          <DropdownMenuItem asChild>
            <Link to={`/${user.username}`} className="flex items-center gap-2">
              <Database className="w-4 h-4" />
              My Schemas
            </Link>
          </DropdownMenuItem>
        )}
        <DropdownMenuItem asChild>
          <Link to="/profile" className="flex items-center gap-2">
            <User className="w-4 h-4" />
            Profile
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link to="/integrations" className="flex items-center gap-2">
            <Plug className="w-4 h-4" />
            Integrations
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <FeedbackDialog>
          <DropdownMenuItem onSelect={(e) => e.preventDefault()} className="flex items-center gap-2 cursor-pointer">
            <MessageSquare className="w-4 h-4" />
            Feedback
          </DropdownMenuItem>
        </FeedbackDialog>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={logout} className="text-destructive focus:text-destructive">
          <LogOut className="w-4 h-4 mr-2" />
          Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
