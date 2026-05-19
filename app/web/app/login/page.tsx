"use client";

import { useState } from "react";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await fetch("/api/auth/callback/credentials", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (res.ok) {
      window.location.href = "/";
    }
  };

  return (
    <div className="max-w-md mx-auto mt-20 p-8 bg-white rounded-xl shadow-sm border border-gray-200">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Sign in to AgentOS</h1>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-agentos-500 focus:border-agentos-500"
            placeholder="admin@agentos.local"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-agentos-500 focus:border-agentos-500"
            placeholder="••••••••"
          />
        </div>
        <button
          type="submit"
          className="w-full py-2 px-4 bg-agentos-600 text-white rounded-lg hover:bg-agentos-700 transition-colors font-medium"
        >
          Sign in
        </button>
      </form>
      <p className="mt-4 text-xs text-gray-500 text-center">
        Demo: admin@agentos.local / agentos
      </p>
    </div>
  );
}
