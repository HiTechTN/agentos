"use client"

import { useState } from "react"
import { Search } from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Sidebar } from "@/components/layout/sidebar"
import { Header } from "@/components/layout/header"

const sessions = [
  { id: "ses-001", project: "ecommerce", workflow: "wf-a1b2", status: "completed", created: "2026-05-22T10:30:00" },
  { id: "ses-002", project: "blog", workflow: "wf-c3d4", status: "running", created: "2026-05-22T10:15:00" },
  { id: "ses-003", project: "dashboard", workflow: "wf-e5f6", status: "completed", created: "2026-05-22T09:45:00" },
  { id: "ses-004", project: "api-docs", workflow: "wf-g7h8", status: "failed", created: "2026-05-22T09:00:00" },
  { id: "ses-005", project: "landing", workflow: "wf-i9j0", status: "pending", created: "2026-05-22T08:30:00" },
  { id: "ses-006", project: "saas", workflow: "wf-k1l2", status: "completed", created: "2026-05-22T08:00:00" },
  { id: "ses-007", project: "mobile-app", workflow: "wf-m3n4", status: "running", created: "2026-05-22T07:45:00" },
  { id: "ses-008", project: "marketing", workflow: "wf-o5p6", status: "completed", created: "2026-05-22T07:00:00" },
]

const statusVariant: Record<string, "success" | "default" | "danger" | "warning"> = {
  completed: "success", running: "default", failed: "danger", pending: "warning",
}

export default function SessionsPage() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [search, setSearch] = useState("")

  const filtered = sessions.filter((s) =>
    s.project.toLowerCase().includes(search.toLowerCase()) ||
    s.id.toLowerCase().includes(search.toLowerCase()),
  )

  return (
    <div className="flex min-h-screen">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex-1 lg:pl-[260px]">
        <Header onMenuClick={() => setSidebarOpen(true)} />
        <main className="p-6 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold gradient-text">Sessions</h1>
              <p className="text-sm text-muted-foreground mt-1">Historique des sessions d'exécution</p>
            </div>
            <div className="relative w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input className="pl-9" placeholder="Rechercher..." value={search} onChange={(e) => setSearch(e.target.value)} />
            </div>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Toutes les sessions</CardTitle>
              <CardDescription>{filtered.length} résultat(s)</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left py-3 px-2 font-medium text-muted-foreground">ID</th>
                      <th className="text-left py-3 px-2 font-medium text-muted-foreground">Projet</th>
                      <th className="text-left py-3 px-2 font-medium text-muted-foreground">Workflow</th>
                      <th className="text-left py-3 px-2 font-medium text-muted-foreground">Statut</th>
                      <th className="text-left py-3 px-2 font-medium text-muted-foreground">Créée le</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((s) => (
                      <tr key={s.id} className="border-b border-border last:border-0 hover:bg-secondary/50 transition-colors">
                        <td className="py-3 px-2 font-medium">{s.id}</td>
                        <td className="py-3 px-2">{s.project}</td>
                        <td className="py-3 px-2 text-muted-foreground">{s.workflow}</td>
                        <td className="py-3 px-2"><Badge variant={statusVariant[s.status]}>{s.status}</Badge></td>
                        <td className="py-3 px-2 text-muted-foreground">{new Date(s.created).toLocaleString("fr-FR")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </main>
      </div>
    </div>
  )
}
