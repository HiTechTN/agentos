"use client"

import { useState } from "react"
import { Bot, Cpu, FileText, Activity, ShoppingCart } from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Sidebar } from "@/components/layout/sidebar"
import { Header } from "@/components/layout/header"

const agents = [
  { name: "DevAgent", icon: Cpu, model: "claude-sonnet-20241022", tasks: 142, status: "idle", lastRun: "2026-05-22T10:30:00", desc: "Analyse, scaffold, code, deploy" },
  { name: "ContentAgent", icon: FileText, model: "gpt-4o-2024-11-20", tasks: 89, status: "running", lastRun: "2026-05-22T10:15:00", desc: "Write, image, publish" },
  { name: "MarketingAgent", icon: Activity, model: "claude-sonnet-20241022", tasks: 56, status: "idle", lastRun: "2026-05-22T09:00:00", desc: "Segment, email, ads, report" },
  { name: "CommerceAgent", icon: ShoppingCart, model: "gpt-4o-2024-11-20", tasks: 73, status: "error", lastRun: "2026-05-22T08:45:00", desc: "Catalog, pricing, checkout, inventory, faq" },
]

export default function AgentsPage() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex min-h-screen">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex-1 lg:pl-[260px]">
        <Header onMenuClick={() => setSidebarOpen(true)} />
        <main className="p-6 space-y-6">
          <div>
            <h1 className="text-2xl font-bold gradient-text">Agents</h1>
            <p className="text-sm text-muted-foreground mt-1">Gestion des agents spécialisés</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {agents.map((a) => (
              <Card key={a.name}>
                <CardHeader className="flex flex-row items-start justify-between">
                  <div className="flex items-start gap-3">
                    <div className="p-2.5 rounded-lg bg-primary/10">
                      <a.icon className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <CardTitle className="text-base">{a.name}</CardTitle>
                      <CardDescription>{a.desc}</CardDescription>
                    </div>
                  </div>
                  <Badge variant={a.status === "running" ? "default" : a.status === "error" ? "danger" : "success"}>
                    {a.status}
                  </Badge>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <p className="text-muted-foreground text-xs">Modèle</p>
                      <p className="font-medium">{a.model}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground text-xs">Tâches</p>
                      <p className="font-medium">{a.tasks}</p>
                    </div>
                    <div className="col-span-2">
                      <p className="text-muted-foreground text-xs">Dernière exécution</p>
                      <p className="font-medium">{new Date(a.lastRun).toLocaleString("fr-FR")}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </main>
      </div>
    </div>
  )
}
