#!/usr/bin/env bash
set -euo pipefail

echo "🚀 AgentOS — Setup UI"
echo "======================"

echo ""
echo "📦 Installing Node.js dependencies..."
npm install

echo ""
echo "🦀 Installing Rust (for Tauri desktop build)..."
if ! command -v rustc &>/dev/null; then
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
  source "$HOME/.cargo/env"
fi

echo ""
echo "🔧 Installing Tauri CLI..."
cargo install tauri-cli --version "^2" 2>/dev/null || true

echo ""
echo "✅ Setup complete!"
echo ""
echo "Commands:"
echo "  npm run dev           — Start web dev server (localhost:3000)"
echo "  npm run build         — Build static site"
echo "  npm run tauri dev     — Start Tauri desktop app (dev)"
echo "  npm run tauri build   — Build desktop app (release)"
