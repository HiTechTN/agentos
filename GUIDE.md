# AgentOS — Guide Complet v5.0

> **Sommaire**
> 1. [Architecture & Concepts](#1-architecture--concepts)
> 2. [Guide de Déploiement](#2-guide-de-déploiement)
> 3. [API Reference](#3-api-reference)
> 4. [Features Détaillées](#4-features-détaillées)
> 5. [Configuration](#5-configuration)
> 6. [Développement](#6-développement)
> 7. [Dépannage](#7-dépannage)

---

## 1. Architecture & Concepts

### 1.1 Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────┐
│                        AgentOS API                          │
│  FastAPI + LangGraph + PostgreSQL + Redis + LLM (OpenAI)    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Dev     │  │ Content  │  │Marketing │  │Commerce  │   │
│  │  Agent   │  │ Agent    │  │ Agent    │  │ Agent    │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │             │             │             │          │
│       └─────────────┴──────┬──────┴─────────────┘          │
│                            │                                │
│                   ┌────────┴────────┐                       │
│                   │   Orchestrator  │                       │
│                   │  (LangGraph)    │                       │
│                   └────────┬────────┘                       │
│                            │                                │
│  ┌──────────┐  ┌──────────┴──────────┐  ┌──────────┐       │
│  │  Memory  │  │  Sub-Agents         │  │  Utils   │       │
│  │  Session │  │  Planner,Verifier   │  │  Auth,   │       │
│  │  Vector  │  │  Explorer,Reviewer  │  │  Cache,  │       │
│  │  Cache   │  │  Debugger           │  │  Rate    │       │
│  └──────────┘  └─────────────────────┘  └──────────┘       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Composants clés

| Composant | Rôle | Technologie |
|-----------|------|-------------|
| **API** | Interface REST + WebSocket | FastAPI 0.115+ |
| **Orchestrator** | Workflow multi-agent | LangGraph + StateGraph |
| **Agents** | Exécution métier spécialisée | Pattern Strategy |
| **Sub-Agents** | Analyse, vérification, debug | LLM + JSON Prompt |
| **Memory** | Persistance + RAG | PostgreSQL + pgvector |
| **LLM Cache** | Cache distribué des réponses LLM | Redis + L1 local |
| **Auth** | Authentification optionnelle | JWT (PyJWT) |
| **Rate Limiting** | Protection des endpoints | slowapi + Redis |
| **MCP** | Model Context Protocol | Server HTTP |

### 1.3 Flux de travail typique

```
POST /api/v1/run  "Crée un site e-commerce"
  │
  ├─▶ Orchestrator.run()
  │   ├─▶ _analyze_prompt()    → LLM décompose la tâche
  │   ├─▶ _route_tasks()       → Ordonnancement
  │   ├─▶ _execute_dev()       → DevAgent.scaffold()
  │   ├─▶ _execute_content()   → ContentAgent.write()
  │   ├─▶ _execute_commerce()  → CommerceAgent.catalog()
  │   └─▶ _finalize()          → Résultat + métriques
  │
  └─▶ Response: {status, session_id, results, errors}
```

### 1.4 Arborescence du projet

```
app/
├── agents/           ← Logique métier des agents
│   ├── base.py       ← Agent de base (Strategy Pattern)
│   ├── dev.py        ← Développement (code, scaffold, deploy)
│   ├── content.py    ← Contenu (write, image, publish)
│   ├── marketing.py  ← Marketing (segment, email, ads)
│   ├── commerce.py   ← Commerce (catalog, pricing, checkout)
│   ├── rules.py      ← Système de règles (AGENTS.md)
│   └── sub_agents/   ← Sous-agents spécialisés
│       └── debugger.py  ← @Debugger
├── config/           ← Configuration & settings
│   └── settings.py   ← Pydantic Settings (variables d'env)
├── memory/           ← Persistance & retrieval
│   ├── session.py    ← Gestion des sessions
│   ├── vector_store.py ← Stockage vectoriel (pgvector)
│   ├── cache.py      ← Cache applicatif
│   └── workspace.py  ← Gestion des workspaces
├── migrations/       ← Alembic (schéma DB)
├── mcp/              ← Model Context Protocol
│   └── server.py     ← Serveur MCP
├── utils/            ← Utilitaires transverses
│   ├── auth.py       ← JWT (create/verify/require)
│   ├── rate_limit.py ← Rate limiting (slowapi + Redis)
│   ├── llm_cache.py  ← Cache LLM persistant (Redis)
│   ├── request_id.py ← X-Request-ID middleware
│   ├── metrics.py    ← Métriques Prometheus
│   ├── telemetry.py  ← Tracing OpenTelemetry
│   ├── logging.py    ← Logger structuré JSON
│   ├── hitl_gateway.py ← Human-In-The-Loop
│   ├── api_clients.py ← Clients LLM (OpenAI/Ollama)
│   ├── sandbox.py    ← Exécution sandboxée
│   └── notifications.py ← Notifications (Slack, Discord)
├── schemas/          ← Schémas Pydantic
│   └── responses.py  ← APIResponse[T] standardisé
├── main.py           ← FastAPI app (routes + middleware)
├── kanban.py         ← Tableau Kanban
├── orchestrator.py   ← Orchestrateur LangGraph
├── pulse.py          ← Dashboard temps réel
└── scheduler.py      ← Planificateur cron
```

---

## 2. Guide de Déploiement

### 2.1 Prérequis

| Ressource | Minimum | Recommandé |
|-----------|---------|------------|
| CPU | 2 cœurs | 4 cœurs |
| RAM | 4 Go | 8 Go |
| Stockage | 20 Go SSD | 50 Go SSD |
| OS | Ubuntu 22.04+ | Ubuntu 24.04 |
| Docker | 24+ | 27+ |
| Docker Compose | 2.0+ | 2.29+ |
| PostgreSQL | 15+ | 17+ (avec pgvector) |
| Redis | 6+ | 7+ |

### 2.2 Déploiement Express (via l'assistant)

Lancez l'application, ouvrez `/deploy` dans votre navigateur :

```
# En local
uv run uvicorn app.main:app --reload
# Puis ouvrez http://localhost:8000/deploy
```

L'assistant vous guide en 3 étapes :

1. **Serveur** — IP, utilisateur SSH, clé privée
2. **API Keys** — OpenRouter, JWT, OpenAI
3. **Services** — PostgreSQL, Redis

Chaque champ a des **guides intégrés** avec liens vers les fournisseurs (DigitalOcean, Hetzner, Supabase, Redis Cloud, etc.).

### 2.3 Déploiement Manuel (pas à pas)

#### Étape 1 : Provisionner un serveur

```bash
# Chez Hetzner (recommandé rapport qualité/prix)
# https://www.hetzner.com/cloud

# Chez DigitalOcean
# https://www.digitalocean.com/

# Configuration de base
ssh root@<IP_DU_SERVEUR>
adduser deploy
usermod -aG sudo deploy
```

#### Étape 2 : Installer Docker

```bash
# Sur le serveur
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker deploy
# Déconnectez-vous et reconnectez-vous
```

#### Étape 3 : Cloner et configurer

```bash
ssh deploy@<IP_DU_SERVEUR>
git clone https://github.com/HiTechTN/agentos.git /opt/agentos
cd /opt/agentos
cp .env.example .env
nano .env   # Configurez vos clés API
```

#### Étape 4 : Démarrer

```bash
docker compose up -d
docker compose logs -f  # Vérifiez les logs
```

### 2.4 Déploiement CI/CD (GitHub Actions)

Le workflow `.github/workflows/docker.yml` exécute :

```
push sur main
  │
  ├─▶ Lint (ruff check + format + mypy)
  ├─▶ Security (bandit)
  ├─▶ Tests (pytest × Python 3.12 + 3.13)
  ├─▶ Docker Build (multi-stage → ghcr.io)
  └─▶ Deploy (SSH → docker compose pull && up)
```

**Secrets GitHub requis :**

| Secret | Description | Obtenir |
|--------|-------------|---------|
| `DEPLOY_HOST` | IP du serveur | Console du VPS |
| `DEPLOY_USER` | Utilisateur SSH | `whoami` |
| `DEPLOY_KEY` | Clé privée SSH | `cat ~/.ssh/id_ed25519` |
| `OPENROUTER_API_KEY` | API key LLM | https://openrouter.ai/keys |
| `DATABASE_URL` | URL PostgreSQL | Voir §5.2 |
| `REDIS_URL` | URL Redis | Voir §5.2 |

```bash
# Configurer avec gh CLI
gh secret set DEPLOY_HOST --repo HiTechTN/agentos --body "192.168.1.42"
gh secret set DEPLOY_USER --repo HiTechTN/agentos --body "deploy"
gh secret set DEPLOY_KEY --repo HiTechTN/agentos --body "$(cat ~/.ssh/id_ed25519)"
```

### 2.5 Externaliser PostgreSQL et Redis

Pour la production, utilisez des services managés :

**PostgreSQL managé :**
- [Supabase](https://supabase.com/) (gratuit 500 Mo, pgvector inclus)
- [ElephantSQL](https://www.elephantsql.com/) (gratuit 20 Mo)
- [Aiven](https://aiven.io/postgresql) (crédit 300 $)

**Redis managé :**
- [Redis Cloud](https://redis.com/try-free/) (gratuit 30 Mo)
- [Upstash](https://upstash.com/) (gratuit 10 Mo)
- [Aiven](https://aiven.io/redis)

### 2.6 Sécurisation

```bash
# Firewall (UFW)
ufw allow 22/tcp      # SSH
ufw allow 80/tcp      # HTTP (derrière reverse proxy)
ufw allow 443/tcp     # HTTPS
ufw deny 8000         # Ne pas exposer FastAPI directement
ufw enable

# Reverse proxy (Nginx + Certbot)
apt install nginx certbot python3-certbot-nginx
# Configurez /etc/nginx/sites-available/agentos
# Puis : certbot --nginx -d votre-domaine.com

# Docker : ne pas exposer les ports internes
# docker-compose.yml → ne pas publier 5432, 6379
```

---

## 3. API Reference

### 3.1 Endpoints

#### Core

| Méthode | Path | Rate Limit | Auth | Description |
|---------|------|-----------|------|-------------|
| `POST` | `/api/v1/run` | configurable | ✓ | Exécuter un prompt |
| `POST` | `/api/v1/plan` | configurable | ✓ | Planifier un workflow |
| `POST` | `/api/v1/verify` | configurable | ✓ | Vérifier un résultat |
| `GET` | `/api/v1/status/{session_id}` | 30/min | ✓ | Statut d'une session |

#### Sub-Agents

| Méthode | Path | Description |
|---------|------|-------------|
| `POST` | `/api/v1/sub-agent/run` | Exécuter un sub-agent |
| `POST` | `/api/v1/sub-agent/debug` | Analyser une erreur (@Debugger) |
| `GET` | `/api/v1/sub-agent/list` | Lister les sub-agents disponibles |

#### HITL (Human-In-The-Loop)

| Méthode | Path | Description |
|---------|------|-------------|
| `POST` | `/api/v1/hitl/approve` | Approuver une action |
| `POST` | `/api/v1/hitl/reject` | Rejeter une action |
| `GET` | `/api/v1/hitl/pending` | Lister les actions en attente |

#### Kanban

| Méthode | Path | Description |
|---------|------|-------------|
| `GET` | `/api/v1/kanban/{project_id}` | Voir le board |
| `POST` | `/api/v1/kanban/{project_id}/card` | Créer une carte |
| `PUT` | `/api/v1/kanban/{project_id}/card/{card_id}/move` | Déplacer une carte |

#### Système

| Méthode | Path | Description |
|---------|------|-------------|
| `GET` | `/health` | Santé (DB, Redis, Ollama) |
| `GET` | `/metrics` | Métriques Prometheus |
| `GET` | `/docs` | Swagger UI |
| `GET` | `/deploy` | Assistant de déploiement |
| `POST` | `/api/v1/deploy/configure` | Configurer les secrets GitHub |

#### Workspaces

| Méthode | Path | Description |
|---------|------|-------------|
| `GET` | `/api/v1/workspaces` | Lister les workspaces |
| `POST` | `/api/v1/workspaces` | Créer un workspace |
| `DELETE` | `/api/v1/workspaces/{ws_id}` | Supprimer un workspace |

### 3.2 Format de réponse

Tous les endpoints retournent :

```json
{
  "data": { ... },
  "meta": {
    "total": 42,
    "page": 1,
    "pages": 3
  },
  "errors": []
}
```

### 3.3 Authentification JWT

```
# 1. Obtenir un token (génération côté serveur)
POST /api/v1/auth/token
{
  "user_id": "alice",
  "workspace_id": "default"
}

# 2. Utiliser le token
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...

# 3. Le middleware auth est OPTIONNEL par défaut
#    → request.state.user est None si pas de token valide
#    → Activez-le via REQUIRE_AUTH=true dans .env
```

### 3.4 Rate Limiting

| Endpoint | Limite par défaut | Configurable |
|----------|------------------|--------------|
| Tous les POST | 30/minute | `RATE_LIMIT_DEFAULT` |
| `/api/v1/run` | 10/minute | `RATE_LIMIT_RUN` |
| `/api/v1/plan` | 20/minute | `RATE_LIMIT_PLAN` |
| `/api/v1/verify` | 15/minute | `RATE_LIMIT_VERIFY` |

Headers de rate limit dans la réponse :
```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 8
X-RateLimit-Reset: 1712345678
```

### 3.5 WebSocket

```
ws://localhost:8000/ws/logs
```

Diffuse les logs structurés en temps réel :

```json
{
  "timestamp": "2026-05-22T12:00:00+00:00",
  "level": "INFO",
  "agent_id": "orchestrator",
  "action": "workflow_start",
  "status": "started",
  "trace_id": "abc-123",
  "project_id": "default",
  "details": { "prompt": "Crée un site..." }
}
```

---

## 4. Features Détaillées

### 4.1 Agents

Chaque agent hérite de `BaseAgent` et implémente `execute(task)`.

| Agent | Actions | Modèle LLM par défaut |
|-------|---------|----------------------|
| **Dev** | `analyze`, `scaffold`, `code`, `deploy` | claude-sonnet |
| **Content** | `write`, `image`, `publish` | GPT-4o |
| **Marketing** | `segment`, `email`, `ads`, `report` | claude-sonnet |
| **Commerce** | `catalog`, `pricing`, `checkout`, `inventory`, `faq` | GPT-4o |

```python
# Exemple : appel direct à un agent
POST /api/v1/run
{
  "prompt": "Crée une landing page pour une startup IA"
}
# Résultat : workflow complet avec résultats de chaque agent
```

### 4.2 Sub-Agents

Sous-agents spécialisés accessibles via `/api/v1/sub-agent/run` :

| Sub-Agent | Rôle | Déclencheurs |
|-----------|------|-------------|
| **@Planner** | Architecture et planification | "plan", "design", "architecture", "approach" |
| **@Verifier** | QA et validation | "verify", "validate", "test", "lint" |
| **@Explorer** | Exploration de code | "explore", "find", "search", "where is" |
| **@CodeReviewer** | Revue de code | "review", "audit", "security" |
| **@Debugger** | Analyse d'erreurs | "error", "exception", "debug", "crash" |

```bash
# Analyser une erreur avec @Debugger
curl -X POST http://localhost:8000/api/v1/sub-agent/debug \
  -H "Content-Type: application/json" \
  -d '{
    "error": "TypeError: expected string or bytes-like object",
    "traceback": "Traceback (most recent call last)...",
    "context": {"file": "app/orchestrator.py", "line": 145}
  }'
```

### 4.3 Human-In-The-Loop (HITL)

Les actions critiques (déploiement, publication) nécessitent approbation humaine.

```python
# Le workflow s'arrête automatiquement et attend
{
  "status": "waiting_hitl",
  "pending_hitl": ["approval-uuid-xxx"],
  "message": "Action 'deploy to prod' requires approval"
}

# Approuver
POST /api/v1/hitl/approve
{ "approval_id": "approval-uuid-xxx" }

# Rejeter
POST /api/v1/hitl/reject
{ "approval_id": "approval-uuid-xxx", "reason": "Pas encore prêt" }
```

### 4.4 Kanban Board

Tableau de bord visuel pour suivre l'avancement :

| Colonne | Description |
|---------|-------------|
| `backlog` | Tâches à faire |
| `todo` | Tâches planifiées |
| `in_progress` | En cours |
| `to_review` | En revue |
| `done` | Terminé |
| `archived` | Archivé |

```python
# Créer une carte
POST /api/v1/kanban/project-123/card
{
  "title": "Déployer le module auth",
  "column": "todo",
  "assignee": "bot"
}

# Voir le board
GET /api/v1/kanban/project-123
```

### 4.5 Pulse (Dashboard)

Données temps réel sur l'activité :

```python
GET /api/v1/pulse/snapshot
# → {
#   "active_agents": 2,
#   "tasks_completed": 15,
#   "tasks_in_progress": 3,
#   "cards_by_column": { "todo": 5, "in_progress": 3, "done": 12 },
#   "agent_activity": { "dev": "running", "content": "idle" }
# }
```

### 4.6 LLM Cache

Cache distribué des réponses LLM :

```
Couche 1 : Cache local (L1) — dictionnaire Python, instantané
Couche 2 : Redis — persistant, partagé entre instances
Durée de vie : 7 jours (configurable)
Clé : SHA256(model + messages + temperature)
```

Configuration :
```env
ENABLE_LLM_CACHE=true
LLM_CACHE_TTL=604800
```

### 4.7 Scheduler

Planification de tâches cron :

```python
POST /api/v1/scheduler/tasks
{
  "name": "Rapport hebdo",
  "cron": "0 9 * * 1",
  "prompt": "Génère le rapport d'activité hebdomadaire",
  "project_id": "default",
  "channel": "slack"
}
```

### 4.8 Git Worktree

Gestion de branches de travail isolées :

```python
POST /api/v1/worktree/create
{ "branch_name": "feature/new-landing", "base": "main" }

POST /api/v1/worktree/rebase
{ "branch_name": "feature/new-landing" }

DELETE /api/v1/worktree/feature/new-landing
```

### 4.9 MCP (Model Context Protocol)

Intégration avec des outils externes via MCP :

```python
POST /api/v1/mcp/register
{
  "name": "github-analyzer",
  "url": "https://mcp.myapp.com/tools"
}

POST /api/v1/mcp/call
{
  "server": "github-analyzer",
  "tool": "analyze_repo",
  "params": { "repo": "HiTechTN/agentos" }
}
```

### 4.10 @Debugger Sub-Agent

Analyse d'erreurs avec suggestions de correction :

```
POST /api/v1/sub-agent/debug
{
  "error": "TypeError: ...",
  "traceback": "...",
  "context": { "file": "app/main.py", "line": 42 }
}

→ {
  "root_cause": "mauvais type dans la fonction x",
  "explanation": "attendu str, reçu None",
  "fix_suggestion": "ajouter un check None",
  "code_patch": "if x is None: return ''",
  "related_files": ["app/main.py"],
  "confidence": 0.92
}
```

### 4.11 Orchestrateur LangGraph

Workflow multi-agent sous forme de graphe d'états :

```
analyze_prompt → route_tasks → execute_dev/execute_content/execute_parallel
                                   ↓
                              check_results → finalize
                                   ↓
                              handle_error → retry | circuit_open | fail
```

Points forts :
- **Circuit Breaker** : 3 échecs consécutifs → arrêt de l'agent
- **Retry automatique** : jusqu'à 3 tentatives par tâche
- **Exécution parallèle** : tâches indépendantes exécutées simultanément
- **HITL propagation** : arrêt sur actions critiques, reprise après approbation

---

## 5. Configuration

### 5.1 Variables d'environnement (.env)

```env
# === Application ===
LOG_LEVEL=INFO
PROJECT_ID=mon-projet
ENVIRONMENT=production
APP_VERSION=5.0.0

# === LLM ===
OPENROUTER_API_KEY=sk-or-v1-xxxxx
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_FALLBACK_MODEL=qwen2.5

# === Modèles ===
MODEL_FOR_CODE=anthropic/claude-sonnet-20241022
MODEL_FOR_CONTENT=openai/gpt-4o-2024-11-20
MODEL_FOR_ANALYSIS=mistralai/mixtral-8x22b-instruct
MODEL_FOR_COMMERCE=openai/gpt-4o-2024-11-20
MODEL_FOR_DEFAULT=openai/gpt-4o-2024-11-20

# === Bases de données ===
DATABASE_URL=postgresql+asyncpg://agentos:password@localhost:5432/agentos
REDIS_URL=redis://:password@localhost:6379/0

# === JWT Auth ===
JWT_SECRET=openssl rand -hex 32
JWT_ALGORITHM=HS256
JWT_EXPIRY_HOURS=24

# === Rate Limiting ===
RATE_LIMIT_DEFAULT=30/minute
RATE_LIMIT_RUN=10/minute
RATE_LIMIT_PLAN=20/minute
RATE_LIMIT_VERIFY=15/minute

# === Cache ===
ENABLE_LLM_CACHE=true
LLM_CACHE_TTL=604800

# === HITL ===
HITL_ENABLED=true
HITL_MODE=webhook_and_cli
HITL_TIMEOUT=3600

# === Scheduler ===
SCHEDULER_ENABLED=true
SCHEDULER_CHECK_INTERVAL=60

# === Service ===
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=agentos
POSTGRES_USER=agentos
POSTGRES_PASSWORD=strong_password
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=
SANDBOX_ENABLED=false
```

### 5.2 Chaînes de connexion

**PostgreSQL (asyncpg) :**
```
postgresql+asyncpg://user:password@host:5432/database
```

**PostgreSQL (avec pgvector, Docker) :**
```
# Docker Compose
postgresql+asyncpg://agentos:password@postgres:5432/agentos
```

**Redis :**
```
# Sans mot de passe
redis://redis:6379/0

# Avec mot de passe
redis://:monpassword@redis:6379/0

# Redis Cloud / Upstash
rediss://default:password@us-east-x.upstash.io:6379
```

### 5.3 Docker Compose

```yaml
version: "3.8"
services:
  app:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [postgres, redis]
  postgres:
    image: pgvector/pgvector:pg17
    environment:
      POSTGRES_DB: agentos
      POSTGRES_USER: agentos
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes: ["pgdata:/var/lib/postgresql/data"]
  redis:
    image: redis:7-alpine
    volumes: ["redisdata:/data"]

volumes: { pgdata: {}, redisdata: {} }
```

---

## 6. Développement

### 6.1 Setup local

```bash
# Prérequis : uv (gestionnaire Python)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Cloner
git clone https://github.com/HiTechTN/agentos.git
cd agentos

# Installer les dépendances (Python 3.13 automatique)
uv sync --frozen

# Configuration minimale
cp .env.example .env
# Éditez .env avec au moins OPENROUTER_API_KEY

# Lancer en dev
uv run uvicorn app.main:app --reload --port 8000
```

### 6.2 Commandes utiles

```bash
# Lancer les tests
uv run pytest app/tests/ -v --tb=short

# Lancer les tests avec couverture
uv run pytest app/tests/ --cov=app --cov-report=term-missing

# Linter
uv run ruff check app/
uv run ruff format app/

# Type checking
uv run mypy app/ --strict

# Sécurité
uv run bandit -r app/ -ll

# Base de données (migrations)
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "description"

# Exporter les dépendances
uv export --no-hashes > requirements.txt

# Ajouter une dépendance
uv add httpx
uv remove httpx
```

### 6.3 Ajouter un agent

```python
# 1. Créer l'agent
# app/agents/mon_agent.py
from app.agents.base import BaseAgent

class MonAgent(BaseAgent):
    async def execute(self, task: dict, session_id: str = "", trace_id: str = "") -> dict:
        # Logique métier
        return {"agent": "mon_agent", "action": task["action"], "success": True, "result": {}}

# 2. Enregistrer dans l'orchestrateur
# app/orchestrator.py → __init__()
self.agents["mon_agent"] = MonAgent()

# 3. Ajouter le nœud au graphe
# app/orchestrator.py → _build_graph()
workflow.add_node("execute_mon_agent", self._execute_mon_agent)

# 4. Ajouter la méthode d'exécution
async def _execute_mon_agent(self, state):
    return await self._execute_agent(state, "mon_agent")
```

### 6.4 Ajouter un sub-agent

```python
# 1. Configurer dans BUILTIN_SUB_AGENTS
# app/agents/sub_agent.py
"mon_sub_agent": SubAgentConfig(
    name="MonSubAgent",
    system_prompt="Tu es un expert en XYZ. Retourne du JSON.",
    model="anthropic/claude-sonnet-20241022",
)

# 2. Ajouter des déclencheurs de routage
# app/agents/sub_agent.py → route_to_sub_agent()
if any(w in task_lower for w in ["keyword1", "keyword2"]):
    return "mon_sub_agent"

# 3. (Optionnel) Créer un sub-agent personnalisé
# ~/.agentos/subagents/mon_sub_agent.md
---
name: MonSubAgent
model: anthropic/claude-sonnet-20241022
tools: [read, search, bash]
---
Tu es un expert. Analyse et retourne du JSON structuré.
```

### 6.5 Migration de base de données

```bash
# Créer une migration automatique
uv run alembic revision --autogenerate -m "add_users_table"

# Vérifier le SQL généré
cat app/migrations/versions/$(ls -t app/migrations/versions/ | head -1)

# Appliquer
uv run alembic upgrade head

# Revenir en arrière
uv run alembic downgrade -1

# Voir l'historique
uv run alembic history
```

---

## 7. Dépannage

### 7.1 Problèmes courants

| Problème | Cause | Solution |
|----------|-------|----------|
| `LLMUnavailableError` | OpenRouter indisponible + Ollama non configuré | Vérifier `OPENROUTER_API_KEY` ou installer Ollama |
| `redis.exceptions.ConnectionError` | Redis non accessible | `docker compose up -d redis` ou vérifier `REDIS_URL` |
| `asyncpg.exceptions.ConnectionError` | PostgreSQL non accessible | `docker compose up -d postgres` ou vérifier `DATABASE_URL` |
| `RateLimitExceeded` | Trop de requêtes | Attendre ou augmenter la limite dans `.env` |
| `ModuleNotFoundError` | uv sync non exécuté | `uv sync --frozen` |
| `Ligne trop longue (E501)` | Style ruff | Ajouter `# noqa: E501` ou configurer `line-length` |
| Tests qui échouent | Redis/PostgreSQL manquant | Lancer les services : `docker compose up -d postgres redis` |

### 7.2 Logs

```bash
# Logs structurés JSON
tail -f /var/log/agentos.log | jq .

# Logs Docker
docker compose logs -f app

# Logs spécifiques
docker compose logs -f app | grep "hitl"
docker compose logs -f app | grep "error"
```

### 7.3 Métriques

```bash
# Prometheus endpoint
curl http://localhost:8000/metrics

# Endpoint santé
curl http://localhost:8000/health
# → {"api": "ok", "database": "ok", "redis": "ok", "ollama": "ok", "version": "5.0.0"}
```

### 7.4 Debugging

```bash
# 1. Vérifier la configuration
uv run python -c "from app.config.settings import get_settings; s=get_settings(); print(s)"

# 2. Tester l'API directement
curl -X POST http://localhost:8000/api/v1/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Dis bonjour"}'

# 3. Analyser une erreur
curl -X POST http://localhost:8000/api/v1/sub-agent/debug \
  -H "Content-Type: application/json" \
  -d '{"error": "...", "traceback": "...", "context": {"file": "app/main.py", "line": 42}}'

# 4. Mode verbose
LOG_LEVEL=DEBUG uv run uvicorn app.main:app --reload
```

---

> **Documentation générée le 22 mai 2026** — AgentOS v5.0.0
> Voir aussi : [README.md](README.md) · [AGENTS.md](AGENTS.md) · [Dockerfile](Dockerfile)
