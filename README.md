# AgentOS v1.0

**AI Agent Orchestration System** · *Système d'Orchestration d'Agents IA*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Build](https://github.com/HiTechTN/agentos/actions/workflows/docker.yml/badge.svg)](https://github.com/HiTechTN/agentos/actions/workflows/docker.yml)
[![Docker](https://img.shields.io/badge/Docker-ghcr.io-blue?logo=docker)](https://github.com/HiTechTN/agentos/pkgs/container/agentos)
[![Docker Web](https://img.shields.io/badge/Docker-web-blue?logo=docker)](https://github.com/HiTechTN/agentos/pkgs/container/agentos%2Fweb)
[![Landing Page](https://img.shields.io/badge/Landing-Pages-purple)](https://hitechtn.github.io/agentos/)

---

## Quick Install · Installation Rapide

```bash
curl -sSL https://raw.githubusercontent.com/HiTechTN/agentos/main/install.sh | bash
```

*Prerequisites: git, docker, docker compose*

---

## Overview · Aperçu

**EN** AgentOS is a lightweight orchestration layer that transforms a user intent into an executable AI workflow through four specialized agents operating in a pipeline: Code → Content → Acquisition → Sales.

**FR** AgentOS est une couche d'orchestration légère transformant une intention utilisateur en workflow IA exécutable via quatre agents spécialisés : Code → Contenu → Acquisition → Vente.

### Architecture

```
User prompt → Orchestrator (LangGraph)
  ├── DevAgent (scaffold, CI/CD, deploy)
  ├── ContentAgent (SEO, images, CMS)
  ├── MarketingAgent (email, ads, analytics)
  └── CommerceAgent (catalog, checkout, inventory)
       ↓
Memory (PostgreSQL + pgvector + Redis)
       ↓
Sandbox → HITL → Output
```

---

## Quick Start · Démarrage Rapide

```bash
# 1. Clone and configure / Cloner et configurer
cp .env.example .env          # Edit your API keys / Modifier vos clés API

# 2. Start the full environment / Démarrer l'environnement complet
make init                     # Build images + seed DB / Build images + seed DB
docker compose up             # Start all services / Lance tous les services
```

### URLs

| Service | URL | Description |
|---------|-----|-------------|
| API | http://localhost:8000 | FastAPI backend |
| API Docs | http://localhost:8000/docs | Swagger UI |
| Dashboard | http://localhost:3000 | Next.js UI |
| MailHog | http://localhost:8025 | Email preview |
| Strapi | http://localhost:1337 | CMS admin |

### Verify · Vérifier

```bash
make test                     # Run tests with coverage / Tests avec couverture
curl http://localhost:8000/health
```

---

## Commands · Commandes

| Command | Description |
|---------|-------------|
| `make up` | Start all services |
| `make down` | Stop all services |
| `make logs` | Follow logs |
| `make test` | Run tests |
| `make lint` | Run ruff + mypy |
| `make seed` | Seed database |
| `make shell` | Open app container shell |
| `make clean` | Clean volumes |
| `make reset` | Full reset (down + clean + up) |
| `make backup` | Backup PostgreSQL |

---

## Environment · Environnement

Copy `.env.example` to `.env` and fill in your API keys:

```bash
OPENROUTER_API_KEY=sk-your-key    # Primary LLM provider
GITHUB_TOKEN=ghp_your-token       # For DevAgent
STRIPE_API_KEY=sk_test_your-key   # For CommerceAgent (test mode)
REPLICATE_API_TOKEN=r8_your-token # For ContentAgent images
```

### Default LLM Models · Modèles par Défaut

| Agent | Model |
|-------|-------|
| DevAgent | Claude Sonnet (anthropic/claude-sonnet-20241022) |
| ContentAgent | GPT-4o (openai/gpt-4o-2024-11-20) |
| MarketingAgent | Claude Sonnet |
| CommerceAgent | GPT-4o |
| Fallback (Ollama) | qwen2.5 |

---

## Features · Fonctionnalités

- **4 Specialized Agents**: Dev, Content, Marketing, Commerce
- **HITL (Human-in-the-Loop)**: Mandatory approval for deploy/publish/charge
- **LLM Fallback**: OpenRouter → Ollama → degraded response
- **Vector Memory**: PostgreSQL + pgvector for embeddings (768d)
- **Redis Cache**: Tiered TTL (60s LLM, 3600s sessions, 86400s projects)
- **JSON Logging**: Immutable structured logs with secret masking
- **Circuit Breaker**: Auto-disable agents after 3 consecutive failures
- **Configurable Priorities**: Task priority system
- **Docker Sandbox**: Isolated agent execution environment

---

## Project Structure · Structure du Projet

```
agentos/
├── docker-compose.yml       # PostgreSQL + Redis + Ollama + Strapi + MailHog
├── Makefile                 # Automation commands
├── .env.example             # Environment template
├── Dockerfile               # App container
└── app/
    ├── main.py              # FastAPI entrypoint
    ├── orchestrator.py      # LangGraph state machine
    ├── agents/              # Agent implementations
    ├── memory/              # Vector store, cache, session
    ├── config/              # Settings, policies, prompts
    ├── utils/               # Logging, HITL, sandbox, API clients
    └── web/                 # Next.js dashboard
```

---

## License · Licence

MIT License — see [LICENSE](LICENSE) file.

---

## Checklist de Livraison

```
╔══════════════════════════════════════════╗
║        CHECKLIST DE LIVRAISON            ║
╠══════════════════════════════════════════╣
║ [✓] Structure de fichiers complète        ║
║ [✓] docker-compose.yml validé             ║
║ [✓] .env.example complet                  ║
║ [✓] HITL implémenté sur deploy/publish    ║
║ [✓] Fallback Ollama opérationnel          ║
║ [✓] Tests couvrant orchestration + HITL  ║
║ [✓] README : 3 commandes de démarrage    ║
║ [✓] Aucun secret en dur                   ║
║ [✓] Logs JSON immuables actifs            ║
╚══════════════════════════════════════════╝
```
