"use client";

import { useState } from "react";
import { AuthProvider, useAuth } from "./AuthContext";
import Header from "./Header";
import ChatPanel from "./ChatPanel";
import PulseDashboard from "./PulseDashboard";
import KanbanBoard from "./KanbanBoard";
import DeployAssistant from "./DeployAssistant";
import AdminPanel from "./AdminPanel";
import Footer from "./Footer";

export type TabId = "chat" | "admin" | "deploy" | "guide";

function DashboardContent() {
  const [activeTab, setActiveTab] = useState<TabId>("chat");
  const { user, isLoading, loginQuick } = useAuth();

  return (
    <div className="flex flex-col min-h-screen">
      <Header activeTab={activeTab} onTabChange={setActiveTab} />

      <main className="flex-1 max-w-[1440px] w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Auth gate for admin tab */}
        {activeTab === "admin" && !user && !isLoading && (
          <div className="flex flex-col items-center justify-center py-16">
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-8 max-w-sm w-full text-center">
              <span className="text-3xl">🔒</span>
              <h2 className="text-sm font-semibold text-gray-200 mt-3">Authentication Required</h2>
              <p className="text-xs text-gray-500 mt-2">Sign in to access the admin panel</p>
              <button
                onClick={loginQuick}
                className="mt-4 px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-500 transition-colors"
              >
                Quick Connect (Dev)
              </button>
            </div>
          </div>
        )}

        {/* Admin panel */}
        {activeTab === "admin" && user && <AdminPanel />}

        {/* Default layout: Chat + Kanban + Pulse + Deploy */}
        {activeTab !== "admin" && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-5 flex flex-col gap-6">
              <ChatPanel />
              <KanbanBoard />
            </div>
            <div className="lg:col-span-7 flex flex-col gap-6">
              <PulseDashboard />
              <DeployAssistant />
            </div>
          </div>
        )}
      </main>

      <Footer />
    </div>
  );
}

export default function Dashboard() {
  return (
    <AuthProvider>
      <DashboardContent />
    </AuthProvider>
  );
}
