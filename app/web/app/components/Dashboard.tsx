"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import AgentStatus from "./AgentStatus";
import LogViewer from "./LogViewer";
import HITLButton from "./HITLButton";

interface PendingApproval {
  id: string;
  session_id: string;
  agent_name: string;
  action: string;
  details: Record<string, unknown>;
  status: string;
  created_at: string;
}

interface AgentResult {
  agent: string;
  action: string;
  success: boolean;
  result?: Record<string, unknown>;
  error?: { code: string; message: string };
}

export default function Dashboard() {
  const [prompt, setPrompt] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("idle");
  const [results, setResults] = useState<AgentResult[]>([]);
  const [pendingHITL, setPendingHITL] = useState<PendingApproval[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/logs`;
    try {
      const ws = new WebSocket(wsUrl);
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          addLog(`[${msg.level}] ${msg.message}`);
        } catch {
          addLog(event.data);
        }
      };
      ws.onopen = () => addLog("WebSocket connected");
      ws.onclose = () => addLog("WebSocket disconnected");
      wsRef.current = ws;
    } catch {
      // WebSocket not available
    }
    return () => {
      wsRef.current?.close();
    };
  }, []);

  const fetchPendingHITL = useCallback(async () => {
    try {
      const res = await fetch("/api/v1/hitl/pending");
      if (res.ok) {
        const data = await res.json();
        setPendingHITL(data.pending || []);
      }
    } catch {
      // silent
    }
  }, []);

  useEffect(() => {
    fetchPendingHITL();
    const interval = setInterval(fetchPendingHITL, 5000);
    return () => clearInterval(interval);
  }, [fetchPendingHITL]);

  const handleSubmit = async () => {
    if (!prompt.trim()) return;
    setStatus("running");
    setResults([]);
    addLog(`Submitting: ${prompt}`);

    try {
      const res = await fetch("/api/v1/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
      const data = await res.json();
      setSessionId(data.session_id || null);
      setStatus(data.status || "completed");
      addLog(`Workflow completed: ${data.status}`);

      if (data.results) {
        const agentResults = Object.values(data.results) as AgentResult[];
        setResults(agentResults);
      }
    } catch (err) {
      setStatus("error");
      addLog(`Error: ${err}`);
    }

    fetchPendingHITL();
  };

  const addLog = (message: string) => {
    setLogs((prev) => [
      ...prev,
      `[${new Date().toISOString()}] ${message}`,
    ]);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Run Workflow
            </h2>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Describe what you want to build..."
              className="w-full h-32 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-agentos-500 focus:border-agentos-500 resize-none"
              disabled={status === "running"}
            />
            <button
              onClick={handleSubmit}
              disabled={status === "running" || !prompt.trim()}
              className="mt-3 px-6 py-2 bg-agentos-600 text-white rounded-lg hover:bg-agentos-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
            >
              {status === "running" ? "Running..." : "Run"}
            </button>
          </div>

          <AgentStatus results={results} />

          <LogViewer logs={logs} />
        </div>

        <div className="space-y-6">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Pending Approvals
            </h2>
            {pendingHITL.length === 0 ? (
              <p className="text-sm text-gray-500">No pending approvals</p>
            ) : (
              <div className="space-y-3">
                {pendingHITL.map((approval) => (
                  <div
                    key={approval.id}
                    className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg"
                  >
                    <p className="text-sm font-medium text-yellow-800">
                      {approval.agent_name}: {approval.action}
                    </p>
                    <p className="text-xs text-yellow-600 mt-1">
                      Session: {approval.session_id.slice(0, 8)}...
                    </p>
                    <HITLButton
                      approvalId={approval.id}
                      onComplete={() => {
                        fetchPendingHITL();
                        addLog(`HITL resolved: ${approval.action}`);
                      }}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              System Status
            </h2>
            <div className="space-y-2">
              <StatusDot label="API" status={status !== "error" ? "ok" : "error"} />
              <StatusDot label="PostgreSQL" status="ok" />
              <StatusDot label="Redis" status="ok" />
              <StatusDot label="Ollama" status="ok" />
              <StatusDot label="Jaeger" status="ok" />
            </div>
            {sessionId && (
              <p className="text-xs text-gray-400 mt-4">
                Session: {sessionId.slice(0, 8)}...
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatusDot({ label, status }: { label: string; status: string }) {
  const color =
    status === "ok"
      ? "bg-green-500"
      : status === "error"
      ? "bg-red-500"
      : "bg-gray-300";
  return (
    <div className="flex items-center gap-2">
      <div className={`w-2 h-2 rounded-full ${color}`} />
      <span className="text-sm text-gray-600">{label}</span>
      <span className="text-xs text-gray-400 ml-auto">{status}</span>
    </div>
  );
}
