#!/usr/bin/env bash
# =============================================================================
# AgentOS v5.1.0 — Quick Install Script
# Usage: curl -sSL https://raw.githubusercontent.com/HiTechTN/agentos/main/install.sh | bash
# =============================================================================
set -euo pipefail

VERSION="5.1.0"
REPO="HiTechTN/agentos"
BRANCH="main"
GH_BASE="https://github.com/$REPO/releases/download/v$VERSION"
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; RED='\033[0;31m'; NC='\033[0m'

echo ""
echo -e "${CYAN}  ╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}  ║     AgentOS v${VERSION} - Install       ║${NC}"
echo -e "${CYAN}  ╚══════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${YELLOW}Choose install method:${NC}"
echo -e "  1) Docker Compose (recommended — full stack)"
echo -e "  2) Linux package (.deb — Debian/Ubuntu)"
echo -e "  3) Linux package (.rpm — Fedora/RHEL)"
echo -e "  4) Python pip (from source)"
echo -e "  5) Desktop app (Tauri)"
echo -e "  6) Download mobile APK"
echo ""
if [ -t 0 ]; then
  read -rp "  Select [1-6] (default: 1): " choice
else
  # When piped (curl | bash), read from terminal directly
  read -rp "  Select [1-6] (default: 1): " choice </dev/tty 2>/dev/null || true
fi
choice="${choice:-1}"

case "$choice" in
  1) install_docker; exit 0 ;;
  2) install_deb; exit 0 ;;
  3) install_rpm; exit 0 ;;
  4) install_pip; exit 0 ;;
  5) install_desktop; exit 0 ;;
  6) download_mobile; exit 0 ;;
  *) echo "Invalid choice"; exit 1 ;;
esac

# =============================================================================
# Docker Compose Install
# =============================================================================
install_docker() {
  echo -e "${YELLOW}[1/4] Checking prerequisites...${NC}"
  command -v git >/dev/null 2>&1 || { echo "Requires git"; exit 1; }; echo "  ✓ git"
  command -v docker >/dev/null 2>&1 || { echo "Requires Docker"; exit 1; }; echo "  ✓ docker"
  docker compose version >/dev/null 2>&1 || { echo "Requires Docker Compose"; exit 1; }; echo "  ✓ docker compose"

  echo -e "${YELLOW}[2/4] Cloning AgentOS...${NC}"
  if [ -d "agentos" ]; then cd agentos && git pull origin "$BRANCH"; else git clone --depth 1 --branch "$BRANCH" "https://github.com/$REPO.git" agentos && cd agentos; fi
  echo "  ✓ Cloned to $(pwd)"

  echo -e "${YELLOW}[3/4] Configuring environment...${NC}"
  [ -f ".env" ] || cp .env.example .env
  echo -e "  ${YELLOW}⚠  Edit .env with your API keys before running.${NC}"

  echo -e "${YELLOW}[4/4] Starting AgentOS...${NC}"
  docker compose pull --quiet 2>/dev/null || true
  docker compose up -d 2>&1 | tail -5 || echo "  ⚠ Some services may have failed"
  show_urls
}

# =============================================================================
# .deb Package Install
# =============================================================================
install_deb() {
  echo -e "${YELLOW}Downloading AgentOS v${VERSION} .deb package...${NC}"
  wget -q "$GH_BASE/agentos_${VERSION}_all.deb" -O /tmp/agentos.deb || curl -sL "$GH_BASE/agentos_${VERSION}_all.deb" -o /tmp/agentos.deb
  echo -e "${YELLOW}Installing...${NC} (requires sudo)"
  sudo dpkg -i /tmp/agentos.deb && sudo apt-get install -f -y 2>/dev/null || true
  echo -e "${GREEN}Installed! Run: sudo agentos init${NC}"
}

# =============================================================================
# .rpm Package Install
# =============================================================================
install_rpm() {
  echo -e "${YELLOW}Downloading AgentOS v${VERSION} .rpm package...${NC}"
  wget -q "$GH_BASE/agentos-${VERSION}-1.noarch.rpm" -O /tmp/agentos.rpm || curl -sL "$GH_BASE/agentos-${VERSION}-1.noarch.rpm" -o /tmp/agentos.rpm
  echo -e "${YELLOW}Installing...${NC} (requires sudo)"
  sudo rpm -ivh /tmp/agentos.rpm || sudo dnf install -y /tmp/agentos.rpm 2>/dev/null || true
  echo -e "${GREEN}Installed! Run: sudo agentos init${NC}"
}

# =============================================================================
# Python pip Install
# =============================================================================
install_pip() {
  echo -e "${YELLOW}Checking prerequisites...${NC}"
  command -v python3 >/dev/null 2>&1 || { echo "Requires Python 3.13+"; exit 1; }
  command -v uv >/dev/null 2>&1 || { curl -LsSf https://astral.sh/uv/install.sh | sh; }

  echo -e "${YELLOW}Cloning & installing AgentOS v${VERSION}...${NC}"
  git clone --depth 1 --branch "$BRANCH" "https://github.com/$REPO.git" agentos 2>/dev/null || true
  cd agentos
  uv sync --all-extras
  echo -e "${GREEN}Installed! Run: uv run uvicorn app.main:app${NC}"
}

# =============================================================================
# Desktop App Download (Tauri)
# =============================================================================
install_desktop() {
  echo -e "${YELLOW}AgentOS Desktop v${VERSION} — Tauri builds:${NC}"
  echo ""
  echo "  Linux:    $GH_BASE/agentos_${VERSION}_amd64.AppImage"
  echo "  Linux:    $GH_BASE/agentos_${VERSION}_amd64.deb"
  echo "  macOS:    $GH_BASE/agentos_${VERSION}_x64.dmg"
  echo "  Windows:  $GH_BASE/agentos_${VERSION}_x64.msi"
  echo ""
  echo -e "${YELLOW}Or build from source:${NC}"
  echo "    git clone https://github.com/$REPO.git"
  echo "    cd agentos/ui && npm install && npm run tauri build"
}

# =============================================================================
# Mobile APK Download
# =============================================================================
download_mobile() {
  echo -e "${YELLOW}AgentOS Mobile APK v${VERSION}:${NC}"
  echo ""
  echo "  $GH_BASE/agentos-mobile-v${VERSION}.apk"
  echo ""
  echo -e "${YELLOW}Or install from EAS:${NC}"
  echo "    npx eas build --platform android --profile preview"
  echo "    (requires EAS account)"
}

# =============================================================================
# URLs
# =============================================================================
show_urls() {
  echo ""
  echo -e "${GREEN}  ╔══════════════════════════════════════╗${NC}"
  echo -e "${GREEN}  ║   AgentOS v${VERSION} is running!        ║${NC}"
  echo -e "${GREEN}  ╚══════════════════════════════════════╝${NC}"
  echo ""
  echo -e "  ${CYAN}API:${NC}        http://localhost:8000"
  echo -e "  ${CYAN}Docs:${NC}       http://localhost:8000/docs"
  echo -e "  ${CYAN}Dashboard:${NC}  http://localhost:3000"
  echo -e "  ${CYAN}MailHog:${NC}    http://localhost:8025"
  echo ""
  echo -e "  ${YELLOW}Quick commands:${NC}"
  echo -e "    cd agentos && docker compose logs -f"
  echo -e "    cd agentos && make test"
  echo ""
}
