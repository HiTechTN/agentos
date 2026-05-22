"use client"

import { useState } from "react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Sidebar } from "@/components/layout/sidebar"
import { Header } from "@/components/layout/header"

export default function SettingsPage() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [apiUrl, setApiUrl] = useState("http://localhost:8000")
  const [openrouterKey, setOpenrouterKey] = useState("")
  const [jwtSecret, setJwtSecret] = useState("")

  return (
    <div className="flex min-h-screen">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex-1 lg:pl-[260px]">
        <Header onMenuClick={() => setSidebarOpen(true)} />
        <main className="p-6 space-y-6">
          <div>
            <h1 className="text-2xl font-bold gradient-text">Paramètres</h1>
            <p className="text-sm text-muted-foreground mt-1">Configuration de l'application</p>
          </div>

          <Card>
            <CardHeader><CardTitle>API</CardTitle><CardDescription>URL et clés d'authentification</CardDescription></CardHeader>
            <CardContent className="space-y-4">
              <Input label="URL de l'API" value={apiUrl} onChange={(e) => setApiUrl(e.target.value)} placeholder="http://localhost:8000" />
              <Input label="Clé OpenRouter" type="password" value={openrouterKey} onChange={(e) => setOpenrouterKey(e.target.value)} placeholder="sk-..." />
              <Input label="JWT Secret" type="password" value={jwtSecret} onChange={(e) => setJwtSecret(e.target.value)} placeholder="Votre secret JWT" />
              <Button size="sm">Enregistrer</Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Modèles LLM</CardTitle><CardDescription>Configuration des modèles par défaut</CardDescription></CardHeader>
            <CardContent className="space-y-4">
              <Input label="Modèle par défaut" value="gpt-4o-2024-11-20" disabled />
              <Input label="Modèle de fallback" value="qwen2.5" disabled />
              <Button size="sm">Enregistrer</Button>
            </CardContent>
          </Card>
        </main>
      </div>
    </div>
  )
}
