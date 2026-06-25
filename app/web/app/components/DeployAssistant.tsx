"use client";

import { useState } from "react";

interface Step {
  id: number;
  title: string;
  icon: string;
  description: string;
  status: "pending" | "active" | "done";
}

export default function DeployAssistant() {
  const [steps, setSteps] = useState<Step[]>([
    {
      id: 1,
      title: "Server",
      icon: "🖥️",
      description: "Configure deployment target and environment",
      status: "done",
    },
    {
      id: 2,
      title: "Keys",
      icon: "🔑",
      description: "Set API keys and secrets",
      status: "active",
    },
    {
      id: 3,
      title: "Deploy",
      icon: "🚀",
      description: "Build, push, and deploy to production",
      status: "pending",
    },
  ]);

  const toggleStep = (stepId: number) => {
    setSteps((prev) =>
      prev.map((s) => {
        if (s.id === stepId) {
          const nextStatus =
            s.status === "done"
              ? "pending"
              : s.status === "pending"
              ? "active"
              : "done";
          return { ...s, status: nextStatus };
        }
        return s;
      })
    );
  };

  const progress = steps.filter((s) => s.status === "done").length;
  const total = steps.length;

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-lg">🚀</span>
          <h2 className="text-sm font-semibold text-gray-200">
            Deploy Assistant
          </h2>
        </div>
        <span className="text-[10px] text-gray-500">
          {progress}/{total} steps
        </span>
      </div>

      {/* Progress bar */}
      <div className="w-full h-1.5 bg-gray-800 rounded-full mb-5 overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-indigo-500 to-emerald-500 rounded-full transition-all duration-500"
          style={{ width: `${(progress / total) * 100}%` }}
        />
      </div>

      {/* Steps */}
      <div className="space-y-3">
        {steps.map((step, index) => (
          <div key={step.id} className="flex gap-3">
            {/* Step connector */}
            <div className="flex flex-col items-center">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm border-2 transition-colors ${
                  step.status === "done"
                    ? "bg-emerald-500/20 border-emerald-500 text-emerald-400"
                    : step.status === "active"
                    ? "bg-indigo-500/20 border-indigo-500 text-indigo-400"
                    : "bg-gray-800 border-gray-700 text-gray-500"
                }`}
                onClick={() => toggleStep(step.id)}
              >
                {step.status === "done" ? "✓" : step.icon}
              </div>
              {index < steps.length - 1 && (
                <div
                  className={`w-0.5 h-6 mt-1 ${
                    step.status === "done"
                      ? "bg-emerald-500/40"
                      : "bg-gray-700"
                  }`}
                />
              )}
            </div>

            {/* Step content */}
            <div className="flex-1 pb-2">
              <div className="flex items-center gap-2">
                <span
                  className={`text-sm font-medium ${
                    step.status === "done"
                      ? "text-emerald-400"
                      : step.status === "active"
                      ? "text-indigo-400"
                      : "text-gray-400"
                  }`}
                >
                  {step.title}
                </span>
                <span
                  className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium ${
                    step.status === "done"
                      ? "bg-emerald-500/10 text-emerald-400"
                      : step.status === "active"
                      ? "bg-indigo-500/10 text-indigo-400"
                      : "bg-gray-800 text-gray-500"
                  }`}
                >
                  {step.status === "done"
                    ? "DONE"
                    : step.status === "active"
                    ? "IN PROGRESS"
                    : "PENDING"}
                </span>
              </div>
              <p className="text-[11px] text-gray-500 mt-0.5">
                {step.description}
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* Deploy button */}
      <button className="w-full mt-5 py-2.5 bg-gradient-to-r from-indigo-600 to-indigo-500 text-white text-sm font-medium rounded-lg hover:from-indigo-500 hover:to-indigo-400 transition-all disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-indigo-500/20">
        {progress === total ? "🚀 Deploy Now" : "Complete all steps first"}
      </button>
    </div>
  );
}
