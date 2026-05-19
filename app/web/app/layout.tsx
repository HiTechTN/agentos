import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AgentOS Dashboard",
  description: "AgentOS v1.0 - AI Agent Orchestration Dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50">
        <nav className="bg-white border-b border-gray-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between h-16 items-center">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-agentos-600 rounded-lg flex items-center justify-center">
                  <span className="text-white font-bold text-sm">A</span>
                </div>
                <span className="font-semibold text-gray-900">AgentOS</span>
              </div>
              <div className="flex items-center gap-4">
                <a href="/login" className="text-sm text-gray-600 hover:text-gray-900">Sign in</a>
                <a href="/" className="text-sm font-medium text-agentos-600 hover:text-agentos-700">Dashboard</a>
              </div>
            </div>
          </div>
        </nav>
        <main>{children}</main>
      </body>
    </html>
  );
}
