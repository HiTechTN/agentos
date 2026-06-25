"use client";

import { useState, useEffect } from "react";

interface Metric {
  label: string;
  value: string;
  change: string;
  positive: boolean;
}

export default function PulseDashboard() {
  const [latencyData] = useState(() =>
    Array.from({ length: 24 }, (_, i) => ({
      x: i,
      y: 20 + Math.sin(i * 0.5) * 15 + Math.random() * 10,
    }))
  );

  const [activityData] = useState(() =>
    Array.from({ length: 24 }, (_, i) => ({
      x: i,
      y: 30 + Math.cos(i * 0.3) * 20 + Math.random() * 15,
    }))
  );

  const [tasksData] = useState(() =>
    Array.from({ length: 7 }, (_, i) => ({
      day: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][i],
      completed: Math.floor(5 + Math.random() * 15),
      failed: Math.floor(Math.random() * 3),
    }))
  );

  const [metrics] = useState<Metric[]>([
    { label: "Avg Latency", value: "142ms", change: "-12%", positive: true },
    { label: "Active Agents", value: "4/4", change: "100%", positive: true },
    { label: "Tasks Today", value: "47", change: "+8", positive: true },
    { label: "Success Rate", value: "98.2%", change: "+0.3%", positive: true },
  ]);

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <span className="text-lg">📊</span>
        <h2 className="text-sm font-semibold text-gray-200">Pulse Dashboard</h2>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
        {metrics.map((m) => (
          <div
            key={m.label}
            className="bg-gray-800/50 rounded-lg p-3 border border-gray-700/50"
          >
            <p className="text-[10px] text-gray-500 uppercase tracking-wider">
              {m.label}
            </p>
            <p className="text-lg font-bold text-gray-100 mt-1">{m.value}</p>
            <p
              className={`text-[10px] mt-0.5 ${
                m.positive ? "text-emerald-400" : "text-red-400"
              }`}
            >
              {m.change}
            </p>
          </div>
        ))}
      </div>

      {/* Charts grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Latency Chart */}
        <div className="bg-gray-800/30 rounded-lg p-4 border border-gray-700/30">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-2 h-2 rounded-full bg-indigo-500" />
            <span className="text-xs font-medium text-gray-300">Latency</span>
          </div>
          <svg viewBox="0 0 200 60" className="w-full h-16">
            <defs>
              <linearGradient id="latencyGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#6366f1" stopOpacity="0.3" />
                <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
              </linearGradient>
            </defs>
            <path
              d={`M ${latencyData
                .map(
                  (d, i) =>
                    `${(i / 23) * 200},${55 - (d.y / 60) * 50}`
                )
                .join(" L ")} L 200,55 L 0,55 Z`}
              fill="url(#latencyGrad)"
            />
            <polyline
              points={latencyData
                .map(
                  (d, i) =>
                    `${(i / 23) * 200},${55 - (d.y / 60) * 50}`
                )
                .join(" ")}
              fill="none"
              stroke="#6366f1"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
          </svg>
        </div>

        {/* Agent Activity Chart */}
        <div className="bg-gray-800/30 rounded-lg p-4 border border-gray-700/30">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-2 h-2 rounded-full bg-emerald-500" />
            <span className="text-xs font-medium text-gray-300">
              Agent Activity
            </span>
          </div>
          <svg viewBox="0 0 200 60" className="w-full h-16">
            <defs>
              <linearGradient id="activityGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#10b981" stopOpacity="0.3" />
                <stop offset="100%" stopColor="#10b981" stopOpacity="0" />
              </linearGradient>
            </defs>
            <path
              d={`M ${activityData
                .map(
                  (d, i) =>
                    `${(i / 23) * 200},${55 - (d.y / 70) * 50}`
                )
                .join(" L ")} L 200,55 L 0,55 Z`}
              fill="url(#activityGrad)"
            />
            <polyline
              points={activityData
                .map(
                  (d, i) =>
                    `${(i / 23) * 200},${55 - (d.y / 70) * 50}`
                )
                .join(" ")}
              fill="none"
              stroke="#10b981"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
          </svg>
        </div>

        {/* Tasks Bar Chart */}
        <div className="bg-gray-800/30 rounded-lg p-4 border border-gray-700/30 lg:col-span-2">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-2 h-2 rounded-full bg-amber-500" />
            <span className="text-xs font-medium text-gray-300">
              Tasks This Week
            </span>
          </div>
          <div className="flex items-end gap-2 h-16">
            {tasksData.map((d) => (
              <div key={d.day} className="flex-1 flex flex-col items-center gap-1">
                <div className="w-full flex gap-0.5 items-end" style={{ height: "40px" }}>
                  <div
                    className="flex-1 bg-indigo-500 rounded-t-sm"
                    style={{ height: `${(d.completed / 20) * 100}%` }}
                  />
                  <div
                    className="flex-1 bg-red-500/60 rounded-t-sm"
                    style={{ height: `${(d.failed / 20) * 100}%` }}
                  />
                </div>
                <span className="text-[9px] text-gray-500">{d.day}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
