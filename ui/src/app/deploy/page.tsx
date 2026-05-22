"use client"

import { useState } from "react"
import { ChevronLeft, ChevronRight, Rocket, Key, Database } from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Sidebar } from "@/components/layout/sidebar"
import { Header } from "@/components/layout/header"

const steps = [
  { id: "server", label: "Serveur", icon: Rocket, desc: "Configurer le serveur de déploiement" },
  { id: "keys", label: "Clés API", icon: Key, desc: "Fournir les clés d'authentification" },
  { id: "services", label: "Services", icon: Database, desc: "Configurer les services de données" },
]

export default function DeployPage() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [step, setStep] = useState(0)
  const [config, setConfig] = useState({ host: "", user: "deploy", key: "", openrouter_api_key: "", jwt_secret: "", openai_api_key: "", database_url: "", redis_url: "" })

  const update = (field: string, value: string) => setConfig((c) => ({ ...c, [field]: value }))

  return (
    <div className="flex min-h-screen">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex-1 lg:pl-[260px]">
        <Header onMenuClick={() => setSidebarOpen(true)} />
        <main className="p-6 space-y-6">
          <div>
            <h1 className="text-2xl font-bold gradient-text">Déploiement</h1>
            <p className="text-sm text-muted-foreground mt-1">Assistant de déploiement en 3 étapes</p>
          </div>

          <div className="flex items-center gap-4 mb-8">
            {steps.map((s, i) => (
              <div key={s.id} className="flex items-center gap-2">
                <div className={`p-2 rounded-lg ${i <= step ? "bg-primary/20 text-primary" : "bg-secondary text-muted-foreground"}`}>
                  <s.icon className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Étape {i + 1}</p>
                  <p className={`text-sm font-medium ${i <= step ? "text-foreground" : "text-muted-foreground"}`}>{s.label}</p>
                </div>
                {i < steps.length - 1 && <ChevronRight className="h-4 w-4 text-muted-foreground/40" />}
              </div>
            ))}
          </div>

          <Card>
            <CardHeader>
              <CardTitle>{steps[step].label}</CardTitle>
              <CardDescription>{steps[step].desc}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {step === 0 && (
                <>
                  <Input label="Hôte" value={config.host} onChange={(e) => update("host", e.target.value)} placeholder="192.168.1.100" />
                  <Input label="Utilisateur SSH" value={config.user} onChange={(e) => update("user", e.target.value)} />
                  <Input label="Clé privée SSH" type="password" value={config.key} onChange={(e) => update("key", e.target.value)} placeholder="-----BEGIN OPENSSH PRIVATE KEY-----" />
                </>
              )}
              {step === 1 && (
                <>
                  <Input label="Clé OpenRouter" value={config.openrouter_api_key} onChange={(e) => update("openrouter_api_key", e.target.value)} placeholder="sk-..." />
                  <Input label="JWT Secret" type="password" value={config.jwt_secret} onChange={(e) => update("jwt_secret", e.target.value)} />
                  <Input label="Clé OpenAI" value={config.openai_api_key} onChange={(e) => update("openai_api_key", e.target.value)} placeholder="sk-..." />
                </>
              )}
              {step === 2 && (
                <>
                  <Input label="URL PostgreSQL" value={config.database_url} onChange={(e) => update("database_url", e.target.value)} placeholder="postgresql://user:pass@host:5432/agentos" />
                  <Input label="URL Redis" value={config.redis_url} onChange={(e) => update("redis_url", e.target.value)} placeholder="redis://user:pass@host:6379" />
                </>
              )}
            </CardContent>
          </Card>

          <div className="flex justify-between">
            <Button variant="outline" disabled={step === 0} onClick={() => setStep((s) => s - 1)}>
              <ChevronLeft className="h-4 w-4 mr-1" /> Précédent
            </Button>
            {step < 2 ? (
              <Button onClick={() => setStep((s) => s + 1)}>
                Suivant <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            ) : (
              <Button onClick={() => alert("Déploiement configuré ! Lancez git push pour déclencher le CI/CD.")}>
                <Rocket className="h-4 w-4 mr-1" /> Configurer
              </Button>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}
