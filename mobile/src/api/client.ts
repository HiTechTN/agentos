import * as SecureStore from 'expo-secure-store';

const TOKEN_KEY = 'agentos_token';
const SERVER_URL_KEY = 'agentos_server_url';

let _offlineEnqueue: ((req: {
  url: string;
  method: string;
  headers: Record<string, string>;
  body?: string;
}) => Promise<void>) | null = null;

export function setOfflineEnqueue(
  fn: typeof _offlineEnqueue,
): void {
  _offlineEnqueue = fn;
}

let _isOnline = true;

export function setOnlineStatus(online: boolean): void {
  _isOnline = online;
}

let _baseUrl = 'http://localhost:8003';
let _token: string | null = null;

export async function loadConfig(): Promise<void> {
  const storedUrl = await SecureStore.getItemAsync(SERVER_URL_KEY);
  const storedToken = await SecureStore.getItemAsync(TOKEN_KEY);
  if (storedUrl) _baseUrl = storedUrl;
  if (storedToken) _token = storedToken;
}

export function getBaseUrl(): string {
  return _baseUrl;
}

export async function setBaseUrl(url: string): Promise<void> {
  _baseUrl = url.replace(/\/+$/, '');
  await SecureStore.setItemAsync(SERVER_URL_KEY, _baseUrl);
}

export function getToken(): string | null {
  return _token;
}

export async function setToken(token: string | null): Promise<void> {
  _token = token;
  if (token) {
    await SecureStore.setItemAsync(TOKEN_KEY, token);
  } else {
    await SecureStore.deleteItemAsync(TOKEN_KEY);
  }
}

export function isAuthenticated(): boolean {
  return _token !== null;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  params?: Record<string, string | number | undefined>;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, params } = opts;
  let url = `${_baseUrl}${path}`;

  if (params) {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined) search.append(k, String(v));
    });
    const qs = search.toString();
    if (qs) url += `?${qs}`;
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (_token) {
    headers['Authorization'] = `Bearer ${_token}`;
  }

  if (!_isOnline && _offlineEnqueue && method !== 'GET') {
    await _offlineEnqueue({
      url,
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    throw new Error('OFFLINE_QUEUED');
  }

  const response = await fetch(url, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API ${response.status}: ${text}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string, params?: Record<string, string | number | undefined>) =>
    request<T>(path, { params }),

  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body }),

  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PUT', body }),

  del: <T>(path: string) =>
    request<T>(path, { method: 'DELETE' }),
};

export interface HealthStatus {
  api: string;
  version?: string;
  database?: string;
  redis?: string;
  ollama?: string;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
}

export interface WorkflowResult {
  result?: string;
  status?: string;
  session_id?: string;
  error?: { code: string; message: string };
}

export interface AgentStatus {
  [name: string]: string;
}

export interface PulseSnapshot {
  [key: string]: unknown;
}

export interface SessionData {
  session_id: string;
  status: string;
  created_at?: string;
  prompt?: string;
  result?: string;
}

export interface PendingApproval {
  id: string;
  action: string;
  agent: string;
  timestamp: string;
}

export interface KanbanBoard {
  columns: Record<string, unknown>;
}

export interface LLMRouterStatus {
  [key: string]: unknown;
}

export async function healthCheck(): Promise<HealthStatus> {
  return api.get<HealthStatus>('/health');
}

export async function login(sub = 'mobile', workspace = 'default'): Promise<string> {
  const resp = await api.post<AuthTokenResponse>('/api/v1/auth/token', { sub, workspace });
  return resp.access_token;
}

export async function runWorkflow(
  prompt: string,
  projectId = 'default',
): Promise<WorkflowResult> {
  return api.post<WorkflowResult>('/api/v1/run', {
    prompt,
    project_id: projectId,
  });
}

export async function getSession(sessionId: string): Promise<SessionData> {
  return api.get<SessionData>(`/api/v1/status/${sessionId}`);
}

export async function getLogs(limit = 100, traceId?: string): Promise<{ logs: unknown[] }> {
  return api.get<{ logs: unknown[] }>('/api/v1/logs', { limit, trace_id: traceId });
}

export async function getPendingApprovals(): Promise<{ pending: PendingApproval[] }> {
  return api.get<{ pending: PendingApproval[] }>('/api/v1/hitl/pending');
}

export async function approveAction(approvalId: string): Promise<{ status: string }> {
  return api.post<{ status: string }>('/api/v1/hitl/approve', { approval_id: approvalId });
}

export async function rejectAction(approvalId: string, reason = ''): Promise<{ status: string }> {
  return api.post<{ status: string }>('/api/v1/hitl/reject', {
    approval_id: approvalId,
    reason,
  });
}

export async function getKanbanBoard(projectId: string): Promise<KanbanBoard> {
  return api.get<KanbanBoard>(`/api/v1/kanban/${projectId}`);
}

export async function getRouterStatus(): Promise<LLMRouterStatus> {
  return api.get<LLMRouterStatus>('/api/v1/llm/router/status');
}

export async function createPlan(goal: string): Promise<{ plan: string }> {
  return api.post<{ plan: string }>('/api/v1/plan', { goal });
}
