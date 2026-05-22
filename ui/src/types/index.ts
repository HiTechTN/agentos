export interface Agent {
  name: string
  status: "idle" | "running" | "error" | "success"
  model: string
  tasks_completed: number
  last_run?: string
}

export interface Session {
  id: string
  project_id: string
  workflow_id: string
  status: "pending" | "running" | "completed" | "failed"
  context: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface Metrics {
  requests_total: number
  requests_p95_ms: number
  active_sessions: number
  agents_online: number
  errors_last_hour: number
}

export interface KanbanCard {
  id: string
  title: string
  description: string
  column: string
  priority: "low" | "medium" | "high" | "critical"
  assignee?: string
  created_at: string
}

export interface PulseSnapshot {
  id: string
  project_id: string
  metrics: Record<string, number>
  timestamp: string
}

export interface ChatMessage {
  id: string
  role: "user" | "assistant" | "system"
  content: string
  timestamp: string
  agent?: string
}

export interface DeployConfig {
  host: string
  user: string
  key?: string
  openrouter_api_key?: string
  jwt_secret?: string
  openai_api_key?: string
  database_url?: string
  redis_url?: string
}
