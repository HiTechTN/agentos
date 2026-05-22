"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import {
  LayoutDashboard, MessageSquare, Bot, History, Columns3,
  Activity, Rocket, BookOpen, Settings, ChevronLeft, X,
} from "lucide-react"

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/dashboard/agents", label: "Agents", icon: Bot },
  { href: "/dashboard/sessions", label: "Sessions", icon: History },
  { href: "/dashboard/kanban", label: "Kanban", icon: Columns3 },
  { href: "/dashboard/pulse", label: "Pulse", icon: Activity },
  { href: "/deploy", label: "Déploiement", icon: Rocket },
  { href: "/guide", label: "Guide", icon: BookOpen },
  { href: "/dashboard/settings", label: "Paramètres", icon: Settings },
]

interface SidebarProps {
  open: boolean
  onClose: () => void
}

export function Sidebar({ open, onClose }: SidebarProps) {
  const pathname = usePathname()

  return (
    <>
      {open && (
        <div className="fixed inset-0 bg-black/50 z-40 lg:hidden" onClick={onClose} />
      )}
      <aside
        className={cn(
          "fixed top-0 left-0 z-50 h-full w-[260px] glass border-r border-border",
          "flex flex-col transition-transform duration-300 lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-center justify-between p-4 border-b border-border">
          <Link href="/" className="flex items-center gap-2">
            <span className="text-2xl">🤖</span>
            <span className="text-lg font-bold gradient-text">AgentOS</span>
          </Link>
          <button onClick={onClose} className="lg:hidden p-1 rounded-md hover:bg-secondary">
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto p-3 space-y-1">
          {navItems.map((item) => {
            const active = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href))
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onClose}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all",
                  active
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary",
                )}
              >
                <item.icon className="h-4.5 w-4.5" />
                {item.label}
              </Link>
            )
          })}
        </nav>

        <div className="p-4 border-t border-border">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="h-2 w-2 rounded-full bg-green-500" />
            <span>v5.0.0</span>
          </div>
        </div>
      </aside>
    </>
  )
}
