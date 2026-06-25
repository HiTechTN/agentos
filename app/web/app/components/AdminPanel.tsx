"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "./AuthContext";

interface ServiceStatus {
  name: string;
  status: "ok" | "error" | "warning";
  detail?: string;
}

interface AdminSettings {
  [key: string]: string | number | boolean;
}

export default function AdminPanel() {
  const { getAuthHeaders, user } = useAuth();
  const [activeSection, setActiveSection] = useState<"services" | "settings" | "llm" | "users">("services");
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [settings, setSettings] = useState<AdminSettings>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchServices = useCallback(async () => {
    try {
      const res = await fetch("/api/v1/admin/services", { headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        const svcList: ServiceStatus[] = [];
        if (data.services?.database) svcList.push({ name: "PostgreSQL", status: data.services.database === "ok" ? "ok" : "error" });
        if (data.services?.redis) svcList.push({ name: "Redis", status: data.services.redis === "ok" ? "ok" : "error" });
        if (data.services?.ollama) svcList.push({ name: "Ollama", status: data.services.ollama?.status === "ok" ? "ok" : "warning", detail: data.services.ollama?.detail });
        if (data.services?.openrouter) svcList.push({ name: "OpenRouter", status: data.services.openrouter?.status === "ok" ? "ok" : "error", detail: `${data.services.openrouter?.models_count || 0} models` });
        setServices(svcList);
      }
    } catch {
      setError("Failed to load services");
    }
  }, [getAuthHeaders]);

  const fetchSettings = useCallback(async () => {
    try {
      const res = await fetch("/api/v1/admin/settings", { headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        setSettings(data.settings || {});
      }
    } catch {
      setError("Failed to load settings");
    }
  }, [getAuthHeaders]);

  useEffect(() => {
    Promise.all([fetchServices(), fetchSettings()]).finally(() => setLoading(false));
  }, [fetchServices, fetchSettings]);

  const sections = [
    { id: "services" as const, label: "Services", icon: "🔧" },
    { id: "settings" as const, label: "Settings", icon: "⚙️" },
    { id: "llm" as const, label: "LLM", icon: "🤖" },
    { id: "users" as const, label: "Users", icon: "👥" },
  ];

  if (loading) {
    return (
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
        <div className="flex items-center gap-2 mb-4">
          <span className="text-lg">⚙️</span>
          <h2 className="text-sm font-semibold text-gray-200">Admin Panel</h2>
        </div>
        <div className="flex items-center justify-center py-8">
          <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          <span className="ml-3 text-sm text-gray-400">Loading admin data...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-lg">⚙️</span>
          <h2 className="text-sm font-semibold text-gray-200">Admin Panel</h2>
        </div>
        {user && (
          <span className="text-[10px] text-gray-500">
            {user.email} · {user.role}
          </span>
        )}
      </div>

      {error && (
        <div className="mb-4 p-2 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-400">
          {error}
        </div>
      )}

      {/* Section tabs */}
      <div className="flex gap-1 mb-4 p-1 bg-gray-800/50 rounded-lg">
        {sections.map((s) => (
          <button
            key={s.id}
            onClick={() => setActiveSection(s.id)}
            className={`flex-1 px-2 py-1.5 rounded-md text-xs font-medium transition-colors ${
              activeSection === s.id
                ? "bg-indigo-600/20 text-indigo-400"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            <span className="mr-1">{s.icon}</span>
            {s.label}
          </button>
        ))}
      </div>

      {/* Content */}
      {activeSection === "services" && (
        <div className="space-y-2">
          {services.length === 0 ? (
            <p className="text-xs text-gray-500 text-center py-4">No services found</p>
          ) : (
            services.map((svc) => (
              <div key={svc.name} className="flex items-center justify-between p-3 bg-gray-800/40 rounded-lg">
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${
                    svc.status === "ok" ? "bg-emerald-500" : svc.status === "warning" ? "bg-amber-500" : "bg-red-500"
                  }`} />
                  <span className="text-xs text-gray-200">{svc.name}</span>
                </div>
                <div className="flex items-center gap-2">
                  {svc.detail && <span className="text-[10px] text-gray-500">{svc.detail}</span>}
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                    svc.status === "ok" ? "bg-emerald-500/10 text-emerald-400" :
                    svc.status === "warning" ? "bg-amber-500/10 text-amber-400" :
                    "bg-red-500/10 text-red-400"
                  }`}>
                    {svc.status.toUpperCase()}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {activeSection === "settings" && (
        <div className="max-h-[300px] overflow-y-auto space-y-1">
          {Object.entries(settings).slice(0, 30).map(([key, value]) => (
            <div key={key} className="flex items-center justify-between py-1.5 px-2 hover:bg-gray-800/30 rounded">
              <span className="text-[11px] text-gray-400 font-mono">{key}</span>
              <span className="text-[11px] text-gray-200 font-mono max-w-[200px] truncate">
                {typeof value === "boolean" ? (value ? "true" : "false") : String(value)}
              </span>
            </div>
          ))}
        </div>
      )}

      {activeSection === "llm" && (
        <div className="text-center py-6">
          <p className="text-xs text-gray-500">LLM Provider Management</p>
          <p className="text-[10px] text-gray-600 mt-1">
            OpenRouter: {settings.openrouter_base_url || "Not configured"}
          </p>
          <div className="mt-3 flex gap-2 justify-center">
            <span className="text-[10px] px-2 py-1 bg-emerald-500/10 text-emerald-400 rounded">
              Dev: {String(settings.dev_agent_model || "N/A")}
            </span>
            <span className="text-[10px] px-2 py-1 bg-indigo-500/10 text-indigo-400 rounded">
              Content: {String(settings.content_agent_model || "N/A")}
            </span>
          </div>
        </div>
      )}

      {activeSection === "users" && (
        <div className="text-center py-6">
          <p className="text-xs text-gray-500">User Management</p>
          <p className="text-[10px] text-gray-600 mt-1">
            Admin emails: {String(settings.admin_emails || "None configured")}
          </p>
        </div>
      )}
    </div>
  );
}
