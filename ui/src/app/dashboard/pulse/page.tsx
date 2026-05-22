"use client"

import { useState } from "react"
import { BarChart3, FolderOpen, Clock } from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Sidebar } from "@/components/layout/sidebar"
import { Header } from "@/components/layout/header"
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts"

const snapshots = Array.from({ length: 20 }, (_, i) => ({
  t: new Date(Date.now() - i * 3600000).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }),
  latency: Math.floor(Math.random() * 200) + 50,
  requests: Math.floor(Math.random() * 60) + 10,
  errors: Math.floor(Math.random() * 8),
})).reverse()

export default function PulsePage() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex min-h-screen">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex-1 lg:pl-[260px]">
        <Header onMenuClick={() => setSidebarOpen(true)} />
        <main className="p-6 space-y-6">
          <div>
            <h1 className="text-2xl font-bold gradient-text">Pulse</h1>
            <p className="text-sm text-muted-foreground mt-1">Métriques en temps réel</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Card><CardHeader className="flex flex-row items-center justify-between pb-2"><CardTitle className="text-sm font-medium text-muted-foreground">Snapshots</CardTitle><BarChart3 className="h-4 w-4 text-muted-foreground" /></CardHeader><CardContent><div className="text-2xl font-bold">{snapshots.length}</div></CardContent></Card>
            <Card><CardHeader className="flex flex-row items-center justify-between pb-2"><CardTitle className="text-sm font-medium text-muted-foreground">Projets actifs</CardTitle><FolderOpen className="h-4 w-4 text-muted-foreground" /></CardHeader><CardContent><div className="text-2xl font-bold">4</div></CardContent></Card>
            <Card><CardHeader className="flex flex-row items-center justify-between pb-2"><CardTitle className="text-sm font-medium text-muted-foreground">Dernière mise à jour</CardTitle><Clock className="h-4 w-4 text-muted-foreground" /></CardHeader><CardContent><div className="text-2xl font-bold">12s</div></CardContent></Card>
          </div>

          <Card>
            <CardHeader><CardTitle>Latence</CardTitle><CardDescription>P95 latency au fil du temps</CardDescription></CardHeader>
            <CardContent>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={snapshots}>
                    <XAxis dataKey="t" stroke="#6e7681" fontSize={12} />
                    <YAxis stroke="#6e7681" fontSize={12} />
                    <Tooltip contentStyle={{ background: "#161b22", border: "1px solid #30363d", borderRadius: 8 }} />
                    <Line type="monotone" dataKey="latency" stroke="#58a6ff" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </main>
      </div>
    </div>
  )
}
