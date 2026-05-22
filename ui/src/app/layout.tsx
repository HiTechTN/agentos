import type { Metadata } from "next"
import { Inter } from "next/font/google"
import { Providers } from "./providers"
import "./globals.css"

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" })

export const metadata: Metadata = {
  title: "AgentOS — Multi-Agent Orchestration Platform",
  description: "Plateforme d'orchestration multi-agent basée sur FastAPI + LangGraph",
  manifest: "/manifest.json",
  themeColor: "#0d1117",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "AgentOS" },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" suppressHydrationWarning>
      <head>
        <link rel="apple-touch-icon" href="/icons/icon-192.png" />
      </head>
      <body className={`${inter.variable} font-sans antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
