#!/usr/bin/env bash
set -euo pipefail

REPO="HiTechTN/agentos"
BRANCH="main"
APP_URL="https://github.com/$REPO"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Default ports (also defined in docker-compose.yml)
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

echo ""
echo -e "${CYAN}  ╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}  ║     AgentOS v5.0.0 - Quick Install     ║${NC}"
echo -e "${CYAN}  ╚══════════════════════════════════════╝${NC}"
echo ""

# --- Prerequisites ---
echo -e "${YELLOW}[1/5] Checking prerequisites...${NC}"

command -v git >/dev/null 2>&1 || { echo "Requires git. Install: apt-get install git"; exit 1; }
echo "  ✓ git"

command -v docker >/dev/null 2>&1 || { echo "Requires Docker. See: https://docs.docker.com/engine/install/"; exit 1; }
echo "  ✓ docker"

docker compose version >/dev/null 2>&1 || docker-compose version >/dev/null 2>&1 || { echo "Requires Docker Compose. See: https://docs.docker.com/compose/install/"; exit 1; }
echo "  ✓ docker compose"

# --- Clone ---
echo -e "${YELLOW}[2/5] Cloning AgentOS...${NC}"
if [ -d "agentos" ]; then
  echo "  Directory 'agentos' already exists. Pulling latest..."
  cd agentos && git pull origin $BRANCH
else
  git clone --depth 1 --branch $BRANCH "$APP_URL.git" agentos
  cd agentos
fi
echo "  ✓ Cloned to $(pwd)"

# --- Environment ---
echo -e "${YELLOW}[3/5] Setting up environment...${NC}"
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo -e "  ${YELLOW}⚠  Edit .env with your API keys before running.${NC}"
  echo -e "  ${YELLOW}   For demo, defaults will work with local fallbacks.${NC}"
else
  echo "  ✓ .env already exists"
fi

# --- Detect available ports ---
echo -e "${YELLOW}[4/5] Checking available ports...${NC}"
AGENTOS_DB_PORT=$(_find_free_port "$AGENTOS_DB_PORT")
AGENTOS_REDIS_PORT=$(_find_free_port "$AGENTOS_REDIS_PORT")
AGENTOS_OLLAMA_PORT=$(_find_free_port "$AGENTOS_OLLAMA_PORT")
AGENTOS_MAILHOG_UI_PORT=$(_find_free_port "$AGENTOS_MAILHOG_UI_PORT")
AGENTOS_MAILHOG_SMTP_PORT=$(_find_free_port "$AGENTOS_MAILHOG_SMTP_PORT")
AGENTOS_STRAPI_PORT=$(_find_free_port "$AGENTOS_STRAPI_PORT")
AGENTOS_JAEGER_UI_PORT=$(_find_free_port "$AGENTOS_JAEGER_UI_PORT")
AGENTOS_JAEGER_OTLP_PORT=$(_find_free_port "$AGENTOS_JAEGER_OTLP_PORT")
AGENTOS_MINIO_API_PORT=$(_find_free_port "$AGENTOS_MINIO_API_PORT")
AGENTOS_MINIO_CONSOLE_PORT=$(_find_free_port "$AGENTOS_MINIO_CONSOLE_PORT")
AGENTOS_API_PORT=$(_find_free_port "$AGENTOS_API_PORT")
AGENTOS_WEB_PORT=$(_find_free_port "$AGENTOS_WEB_PORT")

export AGENTOS_DB_PORT
export AGENTOS_REDIS_PORT
export AGENTOS_OLLAMA_PORT
export AGENTOS_MAILHOG_UI_PORT
export AGENTOS_MAILHOG_SMTP_PORT
export AGENTOS_STRAPI_PORT
export AGENTOS_JAEGER_UI_PORT
export AGENTOS_JAEGER_OTLP_PORT
export AGENTOS_MINIO_API_PORT
export AGENTOS_MINIO_CONSOLE_PORT
export AGENTOS_API_PORT
export AGENTOS_WEB_PORT

echo "  ✓ Ports configured"

# --- Docker Compose ---
echo -e "${YELLOW}  Pulling & building Docker images...${NC} (this may take a while)"
docker compose pull --quiet 2>/dev/null || true
echo "  ✓ Images ready"

# --- Start ---
echo -e "${YELLOW}[5/5] Starting AgentOS...${NC}"
docker compose up -d 2>&1 | tail -10 || {
  echo -e "  ${YELLOW}⚠  Partial startup. Some services may have failed.${NC}"
  echo -e "  ${YELLOW}   Check: docker compose logs --tail=20 <service>${NC}"
}

echo ""
echo -e "${GREEN}  ╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}  ║   AgentOS is running!                ║${NC}"
echo -e "${GREEN}  ╚══════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${CYAN}API:${NC}        http://localhost:${AGENTOS_API_PORT}"
echo -e "  ${CYAN}Dashboard:${NC}  http://localhost:${AGENTOS_WEB_PORT}"
echo -e "  ${CYAN}Docs:${NC}       http://localhost:${AGENTOS_API_PORT}/docs"
echo -e "  ${CYAN}MailHog:${NC}    http://localhost:${AGENTOS_MAILHOG_UI_PORT}"
echo ""
echo -e "  ${YELLOW}Quick commands:${NC}"
echo -e "    cd agentos && docker compose logs -f"
echo -e "    cd agentos && make test"
echo ""
