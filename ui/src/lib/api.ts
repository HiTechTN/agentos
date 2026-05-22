const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("agentos_token") : null
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `API error: ${res.status}`)
  }
  return res.json()
}

export const api = {
  health: () => request<{ api: string; database: string; redis: string; version: string }>("/health"),
  metrics: () => request<{ data: any }>("/api/v1/metrics"),
  sessions: () => request<{ data: any[] }>("/api/v1/sessions"),
  agents: () => request<{ data: any[] }>("/api/v1/agents"),
  chat: (prompt: string, project_id = "default") =>
    request<any>("/api/v1/run", {
      method: "POST",
      body: JSON.stringify({ prompt, project_id }),
    }),
  plan: (prompt: string) =>
    request<any>("/api/v1/plan", {
      method: "POST",
      body: JSON.stringify({ prompt }),
    }),
  kanban: (project_id: string) => request<any[]>(`/api/v1/kanban/${project_id}`),
  pulse: (project_id: string) => request<any[]>(`/api/v1/pulse/${project_id}`),
  deploy: (config: any) =>
    request<any>("/api/v1/deploy/configure", {
      method: "POST",
      body: JSON.stringify(config),
    }),
}
