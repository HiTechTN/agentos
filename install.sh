#!/usr/bin/env bash
set -euo pipefail

REPO="HiTechTN/agentos"
BRANCH="main"
APP_URL="https://github.com/$REPO"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}  ╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}  ║     AgentOS v1.0 - Quick Install     ║${NC}"
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

# --- Docker Compose ---
echo -e "${YELLOW}[4/5] Pulling Docker images...${NC}"
docker compose pull --quiet 2>/dev/null || true
echo "  ✓ Images pulled"

# --- Start ---
echo -e "${YELLOW}[5/5] Starting AgentOS...${NC}"
docker compose up -d 2>&1 | tail -5

echo ""
echo -e "${GREEN}  ╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}  ║   AgentOS is running!                ║${NC}"
echo -e "${GREEN}  ╚══════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${CYAN}API:${NC}        http://localhost:8000"
echo -e "  ${CYAN}Dashboard:${NC}  http://localhost:3000"
echo -e "  ${CYAN}Docs:${NC}       http://localhost:8000/docs"
echo -e "  ${CYAN}MailHog:${NC}    http://localhost:8025"
echo ""
echo -e "  ${YELLOW}Quick commands:${NC}"
echo -e "    cd agentos && docker compose logs -f"
echo -e "    cd agentos && make test"
echo ""
