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
  let normalized = url.trim();
  if (!/^https?:\/\//i.test(normalized)) {
    normalized = 'http://' + normalized;
  }
  _baseUrl = normalized.replace(/\/+$/, '');
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

export interface AttachmentData {
  filename: string;
  mime_type: string;
  data_base64: string;
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

export async function register(
  email: string,
  password: string,
  name?: string,
): Promise<{ id: number; email: string; name?: string }> {
  return api.post<{ id: number; email: string; name?: string }>('/api/v1/auth/register', {
    email,
    password,
    ...(name ? { name } : {}),
  });
}

export async function loginWithCredentials(
  email: string,
  password: string,
): Promise<{ access_token: string; token_type: string; user: { id: number; email: string; name?: string } }> {
  return api.post<{
    access_token: string;
    token_type: string;
    user: { id: number; email: string; name?: string };
  }>('/api/v1/auth/login', { email, password });
}

export async function getMe(): Promise<{ id: number; email: string; name?: string; avatar_url?: string }> {
  return api.get<{ id: number; email: string; name?: string; avatar_url?: string }>('/api/v1/auth/me');
}

export async function runWorkflow(
  prompt: string,
  projectId = 'default',
  attachments?: AttachmentData[],
): Promise<WorkflowResult> {
  return api.post<WorkflowResult>('/api/v1/run', {
    prompt,
    project_id: projectId,
    ...(attachments && attachments.length > 0 ? { attachments } : {}),
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

// ── Admin API ───────────────────────────────────────────────────────────────

export interface AdminSettings {
  [key: string]: string | number | boolean | null;
}

export interface ServiceStatus {
  services: Record<string, string | { status: string; models?: string[]; detail?: string }>;
}

export interface LLMModelInfo {
  id: string;
  name: string;
  context_window: number;
  supports_tools: boolean;
  supports_vision: boolean;
  req_per_min: number;
  req_per_day: number;
}

export interface AdminLLMProviders {
  providers: string[];
  models_by_type: Record<string, LLMModelInfo[]>;
  current_selections: Record<string, string>;
  usage: Record<string, unknown>;
}

export interface AdminUser {
  id: string;
  email: string;
  name?: string;
  avatar_url?: string;
  role: string;
  email_verified: boolean;
  created_at: string;
}

export interface AdminUsersResponse {
  users: AdminUser[];
  total: number;
}

export async function getAdminSettings(): Promise<{ settings: AdminSettings }> {
  return api.get<{ settings: AdminSettings }>('/api/v1/admin/settings');
}

export async function updateAdminSettings(updates: Record<string, string>): Promise<{ status: string; keys: string[] }> {
  return api.put<{ status: string; keys: string[] }>('/api/v1/admin/settings', { updates });
}

export async function getAdminServices(): Promise<ServiceStatus> {
  return api.get<ServiceStatus>('/api/v1/admin/services');
}

export async function getAdminLLMProviders(): Promise<AdminLLMProviders> {
  return api.get<AdminLLMProviders>('/api/v1/admin/llm/providers');
}

export async function testLLMModel(modelId: string, prompt?: string): Promise<{ success: boolean; latency_ms?: number; response?: string; error?: string }> {
  return api.post<{ success: boolean; latency_ms?: number; response?: string; error?: string }>('/api/v1/admin/llm/test', { model_id: modelId, prompt });
}

export async function selectLLMModel(workType: string, modelId: string): Promise<{ status: string; key: string; value: string }> {
  return api.put<{ status: string; key: string; value: string }>('/api/v1/admin/llm/select-model', { work_type: workType, model_id: modelId });
}

export async function getAdminUsers(): Promise<AdminUsersResponse> {
  return api.get<AdminUsersResponse>('/api/v1/admin/users');
}
