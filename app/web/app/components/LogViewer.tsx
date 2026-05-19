"use client";

import { useEffect, useRef } from "react";

export default function LogViewer({ logs }: { logs: string[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  if (logs.length === 0) return null;

  return (
    <div className="bg-gray-900 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-gray-300">Logs</h3>
        <span className="text-xs text-gray-500">{logs.length} entries</span>
      </div>
      <div className="max-h-64 overflow-y-auto space-y-1 font-mono text-xs">
        {logs.map((log, i) => (
          <p key={i} className="text-gray-400">
            {log}
          </p>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
