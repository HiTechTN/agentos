"use client"

import { useState } from "react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Sidebar } from "@/components/layout/sidebar"
import { Header } from "@/components/layout/header"

const initialCards = [
  { id: "1", title: "Analyser le projet", desc: "Revue de l'existant et identification des besoins", column: "todo", priority: "high" as const },
  { id: "2", title: "Configurer CI/CD", desc: "Mettre en place GitHub Actions", column: "todo", priority: "medium" as const },
  { id: "3", title: "Créer l'API Auth", desc: "Endpoints JWT avec refresh tokens", column: "progress", priority: "high" as const },
  { id: "4", title: "Déployer PostgreSQL", desc: "Instance avec pgvector", column: "done", priority: "critical" as const },
  { id: "5", title: "Tests unitaires", desc: "Coverage à 90% minimum", column: "progress", priority: "medium" as const },
  { id: "6", title: "Documentation API", desc: "Swagger + OpenAPI spec", column: "todo", priority: "low" as const },
  { id: "7", title: "Intégration Redis", desc: "Cache LLM + rate limiting", column: "done", priority: "high" as const },
  { id: "8", title: "Monitoring", desc: "Prometheus + Grafana", column: "todo", priority: "low" as const },
]

const priorityColor: Record<string, "default" | "success" | "warning" | "danger"> = {
  low: "default", medium: "default", high: "warning", critical: "danger",
}

const columns = [
  { id: "todo", label: "À faire", color: "border-t-yellow-500" },
  { id: "progress", label: "En cours", color: "border-t-blue-500" },
  { id: "done", label: "Terminé", color: "border-t-green-500" },
]

export default function KanbanPage() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [cards] = useState(initialCards)

  return (
    <div className="flex min-h-screen">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex-1 lg:pl-[260px]">
        <Header onMenuClick={() => setSidebarOpen(true)} />
        <main className="p-6 space-y-6">
          <div>
            <h1 className="text-2xl font-bold gradient-text">Kanban</h1>
            <p className="text-sm text-muted-foreground mt-1">Gestion visuelle des tâches</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {columns.map((col) => (
              <div key={col.id} className={`rounded-xl border border-border border-t-2 ${col.color} bg-card`}>
                <div className="p-4 border-b border-border">
                  <h3 className="font-semibold text-sm">{col.label}</h3>
                  <p className="text-xs text-muted-foreground">{cards.filter((c) => c.column === col.id).length} cartes</p>
                </div>
                <div className="p-3 space-y-3 min-h-[300px]">
                  {cards.filter((c) => c.column === col.id).map((card) => (
                    <div key={card.id} className="p-3 rounded-lg bg-secondary/50 border border-border hover:border-primary/50 transition-all cursor-pointer">
                      <div className="flex items-center justify-between mb-2">
                        <Badge variant={priorityColor[card.priority]}>{card.priority}</Badge>
                      </div>
                      <p className="text-sm font-medium">{card.title}</p>
                      <p className="text-xs text-muted-foreground mt-1">{card.desc}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </main>
      </div>
    </div>
  )
}
