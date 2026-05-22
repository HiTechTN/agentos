"use client"

import { useState } from "react"
import { ExternalLink } from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Sidebar } from "@/components/layout/sidebar"
import { Header } from "@/components/layout/header"

export default function GuidePage() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex min-h-screen">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex-1 lg:pl-[260px]">
        <Header onMenuClick={() => setSidebarOpen(true)} />
        <main className="p-6 space-y-6">
          <div>
            <h1 className="text-2xl font-bold gradient-text">Guide</h1>
            <p className="text-sm text-muted-foreground mt-1">Documentation complète d'AgentOS</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardHeader><CardTitle>📖 Guide interactif</CardTitle><CardDescription>Version web complète avec recherche, sidebar, et exemples de code</CardDescription></CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-4">Architecture, déploiement, API, features, développement, dépannage.</p>
                <a href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/guide`} target="_blank" rel="noopener noreferrer">
                  <Button>Ouvrir le guide <ExternalLink className="h-4 w-4 ml-1" /></Button>
                </a>
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle>🖥️ Desktop App</CardTitle><CardDescription>Application native Tauri v2</CardDescription></CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-4">AgentOS disponible en application de bureau : .deb, .rpm, .AppImage.</p>
                <a href="https://github.com/HiTechTN/agentos/releases" target="_blank" rel="noopener noreferrer">
                  <Button variant="outline">Télécharger <ExternalLink className="h-4 w-4 ml-1" /></Button>
                </a>
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle>📘 API Docs</CardTitle><CardDescription>Documentation Swagger / OpenAPI</CardDescription></CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-4">Tous les endpoints, schémas et exemples interactifs.</p>
                <a href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/docs`} target="_blank" rel="noopener noreferrer">
                  <Button variant="outline">Swagger UI <ExternalLink className="h-4 w-4 ml-1" /></Button>
                </a>
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle>🚀 Assistant déploiement</CardTitle><CardDescription>Interface de configuration du déploiement</CardDescription></CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-4">Configurer votre serveur en 3 étapes.</p>
                <a href="/deploy"><Button variant="outline">Assistant <ExternalLink className="h-4 w-4 ml-1" /></Button></a>
              </CardContent>
            </Card>
          </div>
        </main>
      </div>
    </div>
  )
}
