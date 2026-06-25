"use client";

import { useState } from "react";

interface Task {
  id: string;
  title: string;
  agent: string;
  priority: "high" | "medium" | "low";
}

const initialTasks: Record<string, Task[]> = {
  todo: [
    { id: "t1", title: "Implement WebSocket logs", agent: "dev", priority: "high" },
    { id: "t2", title: "Add rate limiting middleware", agent: "dev", priority: "medium" },
    { id: "t3", title: "Write API documentation", agent: "content", priority: "low" },
  ],
  inProgress: [
    { id: "t4", title: "Dashboard real-time charts", agent: "dev", priority: "high" },
    { id: "t5", title: "Agent memory persistence", agent: "dev", priority: "medium" },
  ],
  done: [
    { id: "t6", title: "Docker health checks", agent: "dev", priority: "high" },
    { id: "t7", title: "JWT auth flow", agent: "dev", priority: "high" },
    { id: "t8", title: "Landing page design", agent: "content", priority: "medium" },
  ],
};

const columns = [
  { id: "todo", label: "ToDo", icon: "📋", color: "text-gray-400" },
  { id: "inProgress", label: "InProg", icon: "🔄", color: "text-amber-400" },
  { id: "done", label: "Done", icon: "✅", color: "text-emerald-400" },
] as const;

const priorityColors = {
  high: "bg-red-500/10 text-red-400 border-red-500/20",
  medium: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  low: "bg-gray-500/10 text-gray-400 border-gray-500/20",
};

export default function KanbanBoard() {
  const [tasks, setTasks] = useState(initialTasks);

  const moveTask = (taskId: string, from: string, to: string) => {
    setTasks((prev) => {
      const task = prev[from as keyof typeof prev].find((t) => t.id === taskId);
      if (!task) return prev;
      return {
        ...prev,
        [from]: prev[from as keyof typeof prev].filter((t) => t.id !== taskId),
        [to]: [...(prev[to as keyof typeof prev] || []), task],
      };
    });
  };

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <span className="text-lg">📋</span>
        <h2 className="text-sm font-semibold text-gray-200">Kanban Board</h2>
      </div>

      {/* Columns */}
      <div className="grid grid-cols-3 gap-3">
        {columns.map((col) => (
          <div key={col.id}>
            <div className="flex items-center gap-1.5 mb-2">
              <span className="text-xs">{col.icon}</span>
              <span className={`text-xs font-medium ${col.color}`}>
                {col.label}
              </span>
              <span className="text-[10px] text-gray-600 ml-auto">
                {tasks[col.id]?.length || 0}
              </span>
            </div>

            <div className="space-y-2 min-h-[120px]">
              {tasks[col.id]?.map((task) => (
                <div
                  key={task.id}
                  className="bg-gray-800/60 rounded-lg p-2.5 border border-gray-700/40 hover:border-gray-600/60 transition-colors cursor-pointer group"
                  onClick={() => {
                    const colIndex = columns.findIndex((c) => c.id === col.id);
                    if (colIndex < columns.length - 1) {
                      moveTask(task.id, col.id, columns[colIndex + 1].id);
                    }
                  }}
                >
                  <p className="text-xs text-gray-200 font-medium leading-tight">
                    {task.title}
                  </p>
                  <div className="flex items-center gap-1.5 mt-1.5">
                    <span
                      className={`text-[9px] px-1.5 py-0.5 rounded border ${priorityColors[task.priority]}`}
                    >
                      {task.priority}
                    </span>
                    <span className="text-[9px] text-gray-500">
                      @{task.agent}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <p className="text-[10px] text-gray-600 mt-3 text-center">
        Click a task to move it forward
      </p>
    </div>
  );
}
