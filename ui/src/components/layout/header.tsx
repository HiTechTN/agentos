"use client"

import { useState, useEffect } from "react"
import { usePathname } from "next/navigation"
import { Menu, GitBranch } from "lucide-react"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth"
import { Button } from "@/components/ui/button"

interface HeaderProps {
  onMenuClick: () => void
}

export function Header({ onMenuClick }: HeaderProps) {
  const pathname = usePathname()
  const { isAuthenticated, user } = useAuth()
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    fetch("/health").then(r => setConnected(r.ok)).catch(() => setConnected(false))
  }, [])

  const crumbs = pathname.split("/").filter(Boolean).map((s, i, a) => ({
    label: s.charAt(0).toUpperCase() + s.slice(1),
    isLast: i === a.length - 1,
  }))

  return (
    <header className="sticky top-0 z-30 glass border-b border-border h-14">
      <div className="flex items-center justify-between h-full px-4">
        <div className="flex items-center gap-3">
          <button onClick={onMenuClick} className="lg:hidden p-1.5 rounded-md hover:bg-secondary">
            <Menu className="h-5 w-5" />
          </button>
          <nav className="flex items-center gap-1.5 text-sm text-muted-foreground">
            {crumbs.length > 0 ? (
              crumbs.map((c, i) => (
                <span key={i} className="flex items-center gap-1.5">
                  {i > 0 && <span className="text-muted-foreground/40">/</span>}
                  <span className={cn(c.isLast && "text-foreground font-medium")}>{c.label}</span>
                </span>
              ))
            ) : (
              <span className="text-foreground font-medium">Dashboard</span>
            )}
          </nav>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span className={cn("h-2 w-2 rounded-full", connected ? "bg-green-500" : "bg-red-500")} />
            {connected ? "Connecté" : "Déconnecté"}
          </div>
          {isAuthenticated ? (
            <span className="text-sm text-muted-foreground">{user?.sub}</span>
          ) : (
            <Button variant="outline" size="sm">Connexion</Button>
          )}
        </div>
      </div>
    </header>
  )
}
