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

# Default ports (same defaults as docker-compose.yml)
AGENTOS_DB_PORT=5432
AGENTOS_REDIS_PORT=6379
AGENTOS_OLLAMA_PORT=11434
AGENTOS_MAILHOG_UI_PORT=8025
AGENTOS_MAILHOG_SMTP_PORT=1025
AGENTOS_STRAPI_PORT=1337
AGENTOS_JAEGER_UI_PORT=16686
AGENTOS_JAEGER_OTLP_PORT=4318
AGENTOS_MINIO_API_PORT=9000
AGENTOS_MINIO_CONSOLE_PORT=9001
AGENTOS_API_PORT=8000
AGENTOS_WEB_PORT=3000

# =============================================================================
# Helper: find a free port starting from the given base
# =============================================================================
_find_free_port() {
  local base_port=$1
  local port=$base_port
  if command -v ss >/dev/null 2>&1; then
    while ss -tlnp "sport = :$port" 2>/dev/null | grep -q LISTEN; do
      port=$((port + 1))
    done
  else
    while (: < /dev/tcp/127.0.0.1/"$port") 2>/dev/null; do
      port=$((port + 1))
    done
  fi
  echo "$port"
}

# =============================================================================
# Helper: assign free ports for all services, export them for docker-compose
# =============================================================================
_assign_free_ports() {
  # Source existing .env if present to preserve user overrides
  [ -f .env ] && set -a && source .env && set +a 2>/dev/null || true
  # Only assign if the default port is actually in use
  AGENTOS_DB_PORT=$(_find_free_port "${AGENTOS_DB_PORT:-5432}")
  AGENTOS_REDIS_PORT=$(_find_free_port "${AGENTOS_REDIS_PORT:-6379}")
  AGENTOS_OLLAMA_PORT=$(_find_free_port "${AGENTOS_OLLAMA_PORT:-11434}")
  AGENTOS_MAILHOG_UI_PORT=$(_find_free_port "${AGENTOS_MAILHOG_UI_PORT:-8025}")
  AGENTOS_MAILHOG_SMTP_PORT=$(_find_free_port "${AGENTOS_MAILHOG_SMTP_PORT:-1025}")
  AGENTOS_STRAPI_PORT=$(_find_free_port "${AGENTOS_STRAPI_PORT:-1337}")
  AGENTOS_JAEGER_UI_PORT=$(_find_free_port "${AGENTOS_JAEGER_UI_PORT:-16686}")
  AGENTOS_JAEGER_OTLP_PORT=$(_find_free_port "${AGENTOS_JAEGER_OTLP_PORT:-4318}")
  AGENTOS_MINIO_API_PORT=$(_find_free_port "${AGENTOS_MINIO_API_PORT:-9000}")
  AGENTOS_MINIO_CONSOLE_PORT=$(_find_free_port "${AGENTOS_MINIO_CONSOLE_PORT:-9001}")
  AGENTOS_API_PORT=$(_find_free_port "${AGENTOS_API_PORT:-8000}")
  AGENTOS_WEB_PORT=$(_find_free_port "${AGENTOS_WEB_PORT:-3000}")

  export AGENTOS_DB_PORT AGENTOS_REDIS_PORT AGENTOS_OLLAMA_PORT
  export AGENTOS_MAILHOG_UI_PORT AGENTOS_MAILHOG_SMTP_PORT AGENTOS_STRAPI_PORT
  export AGENTOS_JAEGER_UI_PORT AGENTOS_JAEGER_OTLP_PORT
  export AGENTOS_MINIO_API_PORT AGENTOS_MINIO_CONSOLE_PORT
  export AGENTOS_API_PORT AGENTOS_WEB_PORT
}

# =============================================================================
# Docker Compose Install
# =============================================================================
install_docker() {
  echo -e "${YELLOW}[1/4] Checking prerequisites...${NC}"
  command -v git >/dev/null 2>&1 || { echo "Requires git"; exit 1; }; echo "  ✓ git"
  command -v docker >/dev/null 2>&1 || { echo "Requires Docker"; exit 1; }; echo "  ✓ docker"
  docker compose version >/dev/null 2>&1 || { echo "Requires Docker Compose"; exit 1; }; echo "  ✓ docker compose"

  echo -e "${YELLOW}[2/4] Setting up AgentOS...${NC}"
  if [ -d "agentos" ]; then
    echo "  Updating existing installation..."
    cd agentos
    [ -f .env ] && cp .env /tmp/agentos_env_backup
    git fetch origin "$BRANCH" 2>&1
    git stash --include-untracked 2>/dev/null || true
    git reset --hard "origin/$BRANCH" 2>&1
    git clean -fd 2>/dev/null || true
    [ -f /tmp/agentos_env_backup ] && mv /tmp/agentos_env_backup .env
    echo "  ✓ Updated to latest commit"
  else
    echo "  Cloning AgentOS..."
    git clone --depth 1 --branch "$BRANCH" "https://github.com/$REPO.git" agentos
    cd agentos
  fi
  echo "  ✓ $(pwd)"

  echo -e "${YELLOW}[3/4] Configuring environment...${NC}"
  [ -f ".env" ] || cp .env.example .env
  echo -e "  ${YELLOW}⚠  Edit .env with your API keys before running.${NC}"

  echo -e "${YELLOW}[4/4] Starting AgentOS...${NC}"
  if [ -f ".env" ]; then
    # Existing install — keep the same ports from .env
    set -a; source .env; set +a 2>/dev/null || true
    echo "  Using existing port configuration"
  else
    # Fresh install — auto-detect free ports
    _assign_free_ports
  fi

  # Check for local Ollama — skip Docker Ollama if already running
  _local_ollama=false
  if command -v curl >/dev/null 2>&1 && curl -s --max-time 2 http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} Local Ollama detected at http://localhost:11434"
    _local_ollama=true
  fi

  echo "  Ports: API=${AGENTOS_API_PORT} DB=${AGENTOS_DB_PORT} Web=${AGENTOS_WEB_PORT}"
  docker compose down 2>/dev/null || true

  if [ "$_local_ollama" = true ]; then
    # Override compose — skip Docker Ollama, point app to host Ollama
    cat > docker-compose.override.yml << 'OVERRIDE'
services:
  ollama:
    profiles: ["disabled"]
  app:
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      OLLAMA_BASE_URL: http://host.docker.internal:11434
OVERRIDE
    echo -e "  ${GREEN}✓${NC} Created docker-compose.override.yml for local Ollama"
  fi

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

  echo -e "${YELLOW}Setting up AgentOS v${VERSION}...${NC}"
  if [ -d "agentos" ]; then
    echo "  Updating existing installation..."
    cd agentos
    [ -f .env ] && cp .env /tmp/agentos_env_backup
    git fetch origin "$BRANCH" 2>&1
    git stash --include-untracked 2>/dev/null || true
    git reset --hard "origin/$BRANCH" 2>&1
    git clean -fd 2>/dev/null || true
    [ -f /tmp/agentos_env_backup ] && mv /tmp/agentos_env_backup .env
    echo "  ✓ Updated to latest commit"
  else
    echo "  Cloning AgentOS..."
    git clone --depth 1 --branch "$BRANCH" "https://github.com/$REPO.git" agentos
    cd agentos
  fi
  uv sync --all-extras
  echo -e "${GREEN}Installed! Run: uv run uvicorn app.main:app${NC}"
}

# =============================================================================
# Desktop App Download (Tauri)
# =============================================================================
install_desktop() {
  echo -e "${YELLOW}AgentOS Desktop v${VERSION} — Tauri builds:${NC}"
  echo ""
  echo "  Linux:    $GH_BASE/AgentOS_${VERSION}_amd64.AppImage"
  echo "  Linux:    $GH_BASE/AgentOS_${VERSION}_amd64.deb"
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
  echo -e "  ${CYAN}API:${NC}        http://localhost:${AGENTOS_API_PORT}"
  echo -e "  ${CYAN}Docs:${NC}       http://localhost:${AGENTOS_API_PORT}/docs"
  echo -e "  ${CYAN}Dashboard:${NC}  http://localhost:${AGENTOS_WEB_PORT}"
  echo -e "  ${CYAN}MailHog:${NC}    http://localhost:${AGENTOS_MAILHOG_UI_PORT}"
  echo ""
  echo -e "  ${YELLOW}Quick commands:${NC}"
  echo -e "    cd agentos && docker compose logs -f"
  echo -e "    cd agentos && make test"
  echo ""
}

# =============================================================================
# Main Menu
# =============================================================================
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
# Accept choice as CLI argument, or prompt interactively
if [ $# -ge 1 ] && [[ "$1" =~ ^[1-6]$ ]]; then
  choice="$1"
elif [ -t 0 ]; then
  read -rp "  Select [1-6] (default: 1): " choice
else
  # When piped (curl | bash), show prompt and try to read from terminal
  echo -n "  Select [1-6] (default: 1): " >&2
  { read -r choice </dev/tty; } 2>/dev/null || choice=""
fi
choice="${choice:-1}"

case "$choice" in
  1) install_docker ;;
  2) install_deb ;;
  3) install_rpm ;;
  4) install_pip ;;
  5) install_desktop ;;
  6) download_mobile ;;
  *) echo "Invalid choice"; exit 1 ;;
esac
