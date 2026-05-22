"use client"

import { useState } from "react"
import { Activity, Clock, Users, AlertCircle, ArrowUp, Bot, Cpu, FileText, ShoppingCart } from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Sidebar } from "@/components/layout/sidebar"
import { Header } from "@/components/layout/header"
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts"

const sparklineData = Array.from({ length: 24 }, (_, i) => ({ h: i, v: Math.floor(Math.random() * 100) + 20 }))

function StatCard({ icon: Icon, label, value, sub, trend }: any) {
  return (
    <Card className="relative overflow-hidden">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        <div className="flex items-center gap-1 mt-1 text-xs text-muted-foreground">
          {trend && <ArrowUp className="h-3 w-3 text-green-500" />}
          {sub}
        </div>
      </CardContent>
      <div className="absolute bottom-0 left-0 right-0 h-12 opacity-30">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={sparklineData}>
            <Area type="monotone" dataKey="v" stroke="#58a6ff" fill="#58a6ff" strokeWidth={1.5} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}

const recentSessions = [
  { id: "ses-001", project: "ecommerce", status: "completed", created: "2026-05-22T10:30:00" },
  { id: "ses-002", project: "blog", status: "running", created: "2026-05-22T10:15:00" },
  { id: "ses-003", project: "dashboard", status: "completed", created: "2026-05-22T09:45:00" },
  { id: "ses-004", project: "api-docs", status: "failed", created: "2026-05-22T09:00:00" },
  { id: "ses-005", project: "landing", status: "pending", created: "2026-05-22T08:30:00" },
]

const agents = [
  { name: "DevAgent", icon: Cpu, model: "claude-sonnet", tasks: 142, status: "idle" },
  { name: "ContentAgent", icon: FileText, model: "gpt-4o", tasks: 89, status: "running" },
  { name: "MarketingAgent", icon: Activity, model: "claude-sonnet", tasks: 56, status: "idle" },
  { name: "CommerceAgent", icon: ShoppingCart, model: "gpt-4o", tasks: 73, status: "idle" },
]

const chartData = Array.from({ length: 12 }, (_, i) => ({
  time: `${i * 2}h`,
  requests: Math.floor(Math.random() * 80) + 20,
  errors: Math.floor(Math.random() * 5),
}))

export default function DashboardPage() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex min-h-screen">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex-1 lg:pl-[260px]">
        <Header onMenuClick={() => setSidebarOpen(true)} />
        <main className="p-6 space-y-6">
          <div>
            <h1 className="text-2xl font-bold gradient-text">Dashboard</h1>
            <p className="text-sm text-muted-foreground mt-1">Vue d'ensemble de votre plateforme AgentOS</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard icon={Activity} label="Requêtes" value="1,284" sub="Dernières 24h" trend />
            <StatCard icon={Clock} label="P95 Latence" value="342ms" sub="-12% vs hier" />
            <StatCard icon={Users} label="Sessions actives" value="7" sub="3 en cours" />
            <StatCard icon={AlertCircle} label="Erreurs" value="12" sub="Dernière heure" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Activité</CardTitle>
                <CardDescription>Requêtes et erreurs (24h)</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData}>
                      <XAxis dataKey="time" stroke="#6e7681" fontSize={12} />
                      <YAxis stroke="#6e7681" fontSize={12} />
                      <Tooltip
                        contentStyle={{ background: "#161b22", border: "1px solid #30363d", borderRadius: 8 }}
                      />
                      <Area type="monotone" dataKey="requests" stroke="#58a6ff" fill="#58a6ff" fillOpacity={0.1} strokeWidth={2} />
                      <Area type="monotone" dataKey="errors" stroke="#f85149" fill="#f85149" fillOpacity={0.1} strokeWidth={2} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Sessions récentes</CardTitle>
                <CardDescription>Les 5 dernières sessions</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {recentSessions.map((s) => (
                    <div key={s.id} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                      <div>
                        <p className="text-sm font-medium">{s.project}</p>
                        <p className="text-xs text-muted-foreground">{s.id}</p>
                      </div>
                      <Badge variant={s.status === "completed" ? "success" : s.status === "running" ? "default" : s.status === "failed" ? "danger" : "warning"}>
                        {s.status}
                      </Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-4">Agents</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {agents.map((a) => (
                <Card key={a.name}>
                  <CardHeader className="flex flex-row items-center justify-between pb-2">
                    <CardTitle className="text-sm font-medium">{a.name}</CardTitle>
                    <a.icon className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`h-2 w-2 rounded-full ${a.status === "running" ? "bg-blue-500 animate-pulse" : "bg-green-500"}`} />
                      <span className="text-xs text-muted-foreground">{a.model}</span>
                    </div>
                    <p className="text-xs text-muted-foreground">{a.tasks} tâches</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
