import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AgentOS v7.0 Dashboard",
  description: "AgentOS v7.0 - AI Agent Orchestration Dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">
        {children}
      </body>
    </html>
  );
}
