"use client"

import { useState, useRef, useEffect } from "react"
import { Send, Bot, User, Loader2 } from "lucide-react"
import { Sidebar } from "@/components/layout/sidebar"
import { Header } from "@/components/layout/header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { ChatMessage } from "@/types"

const initialMessages: ChatMessage[] = [
  { id: "0", role: "assistant", content: "Bonjour ! Je suis l'interface AgentOS. Posez-moi une question ou donnez-moi une tâche à exécuter.", timestamp: new Date().toISOString() },
]

export default function ChatPage() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages)
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }) }, [messages])

  const send = async () => {
    if (!input.trim() || loading) return
    const userMsg: ChatMessage = { id: Date.now().toString(), role: "user", content: input, timestamp: new Date().toISOString() }
    setMessages((m) => [...m, userMsg])
    setInput("")
    setLoading(true)

    setTimeout(() => {
      const assistantMsg: ChatMessage = {
        id: (Date.now() + 1).toString(), role: "assistant",
        content: `J'ai bien reçu votre demande : "${userMsg.content}". Dans une version connectée, cette requête serait envoyée à l'API AgentOS pour exécution.`,
        timestamp: new Date().toISOString(), agent: "AgentOS",
      }
      setMessages((m) => [...m, assistantMsg])
      setLoading(false)
    }, 1200)
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex-1 lg:pl-[260px] flex flex-col">
        <Header onMenuClick={() => setSidebarOpen(true)} />
        <div className="flex-1 flex flex-col max-w-4xl mx-auto w-full p-4">
          <div className="flex-1 overflow-y-auto space-y-4 mb-4">
            {messages.map((msg) => (
              <div key={msg.id} className={`flex gap-3 ${msg.role === "user" ? "justify-end" : ""}`}>
                {msg.role !== "user" && (
                  <div className="p-2 rounded-lg bg-primary/10 h-fit">
                    <Bot className="h-5 w-5 text-primary" />
                  </div>
                )}
                <div className={`max-w-[70%] p-4 rounded-xl ${
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "glass border border-border"
                }`}>
                  <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                  {msg.agent && <p className="text-xs text-muted-foreground mt-2">via {msg.agent}</p>}
                </div>
                {msg.role === "user" && (
                  <div className="p-2 rounded-lg bg-secondary h-fit">
                    <User className="h-5 w-5 text-muted-foreground" />
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="flex gap-3">
                <div className="p-2 rounded-lg bg-primary/10"><Bot className="h-5 w-5 text-primary" /></div>
                <div className="glass border border-border rounded-xl p-4"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          <div className="flex gap-2">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
              placeholder="Posez votre question ou décrivez votre tâche..."
              className="flex-1"
            />
            <Button onClick={send} loading={loading}><Send className="h-4 w-4" /></Button>
          </div>
        </div>
      </div>
    </div>
  )
}
