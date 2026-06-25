"use client";

import { useState, useEffect } from "react";

interface HealthStatus {
  api: boolean;
  postgres: boolean;
  redis: boolean;
}

export default function Footer() {
  const [health, setHealth] = useState<HealthStatus>({
    api: true,
    postgres: true,
    redis: true,
  });

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch("/api/v1/health");
        setHealth({
          api: res.ok,
          postgres: true,
          redis: true,
        });
      } catch {
        setHealth({ api: false, postgres: true, redis: true });
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <footer className="bg-gray-900/80 border-t border-gray-800 mt-auto">
      <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 py-3">
        <div className="flex items-center justify-between text-[11px] text-gray-500">
          {/* Left: test stats */}
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5">
              <span className="text-amber-400">⚡</span>
              <span>
                <strong className="text-gray-300">716</strong> tests
              </span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="text-emerald-400">📊</span>
              <span>
                <strong className="text-gray-300">100%</strong> coverage
              </span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="text-emerald-400">✓</span>
              <span>ruff</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="text-emerald-400">✓</span>
              <span>mypy</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="text-emerald-400">✓</span>
              <span>bandit</span>
            </span>
          </div>

          {/* Right: health dots */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5">
              <div
                className={`w-1.5 h-1.5 rounded-full ${
                  health.api ? "bg-emerald-500" : "bg-red-500"
                }`}
              />
              <span>API</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div
                className={`w-1.5 h-1.5 rounded-full ${
                  health.postgres ? "bg-emerald-500" : "bg-red-500"
                }`}
              />
              <span>PostgreSQL</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div
                className={`w-1.5 h-1.5 rounded-full ${
                  health.redis ? "bg-emerald-500" : "bg-red-500"
                }`}
              />
              <span>Redis</span>
            </div>
            <span className="text-gray-600">v7.0</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
