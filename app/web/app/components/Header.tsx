"use client";

import type { TabId } from "./Dashboard";

const tabs: { id: TabId; label: string; icon: string }[] = [
  { id: "chat", label: "Chat", icon: "💬" },
  { id: "admin", label: "Admin", icon: "⚙️" },
  { id: "deploy", label: "Deploy", icon: "🚀" },
  { id: "guide", label: "Guide", icon: "📖" },
];

export default function Header({
  activeTab,
  onTabChange,
}: {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
}) {
  return (
    <header className="bg-gray-900 border-b border-gray-800 sticky top-0 z-50">
      <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          {/* Logo + Title */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <span className="text-white font-bold text-sm">A</span>
            </div>
            <div>
              <h1 className="text-sm font-semibold text-white leading-none">
                AgentOS v7.0 Dashboard
              </h1>
              <p className="text-[10px] text-gray-500 mt-0.5">
                AI Agent Orchestration
              </p>
            </div>
          </div>

          {/* Nav Tabs */}
          <nav className="flex items-center gap-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => onTabChange(tab.id)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  activeTab === tab.id
                    ? "bg-indigo-600/20 text-indigo-400 border border-indigo-500/30"
                    : "text-gray-400 hover:text-gray-200 hover:bg-gray-800"
                }`}
              >
                <span className="mr-1.5">{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </nav>

          {/* Status indicator */}
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs text-gray-500">All systems operational</span>
          </div>
        </div>
      </div>
    </header>
  );
}
