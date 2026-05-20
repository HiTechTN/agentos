<p align="center">
  <img src="https://img.shields.io/badge/AgentOS-v3.0.0-4c6ef5?style=for-the-badge&logo=python&logoColor=white" alt="Version">
  <img src="https://img.shields.io/github/actions/workflow/status/HiTechTN/agentos/docker.yml?style=for-the-badge&logo=githubactions&logoColor=white&label=Build" alt="Build">
  <img src="https://img.shields.io/github/license/HiTechTN/agentos?style=for-the-badge&logo=opensourceinitiative&logoColor=white" alt="License">
  <img src="https://img.shields.io/badge/docker%20compose-up-blue?style=for-the-badge&logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/Observability-Jaeger-29BEB0?style=for-the-badge&logo=grafana&logoColor=white" alt="Jaeger">
  <img src="https://img.shields.io/badge/Storage-S3_Friendly-569A31?style=for-the-badge&logo=minio&logoColor=white" alt="MinIO">
</p>

<h1 align="center">🤖 AgentOS</h1>
<p align="center"><b>AI Agent Orchestration System</b> · Transformez une intention en workflow IA exécutable</p>

<p align="center">
  <a href="#-quick-install">🚀 Quick Install</a> •
  <a href="#-architecture">🏗️ Architecture</a> •
  <a href="#-agents">🎯 Agents</a> •
  <a href="#-features">⚡ Features</a> •
  <a href="#-quick-start">📖 Quick Start</a> •
  <a href="#-api">📡 API</a>
</p>

<br>

---

## 🚀 Quick Install

```bash
curl -sSL https://raw.githubusercontent.com/HiTechTN/agentos/main/install.sh | bash
```

<details>
<summary><b>⚙️ What this does</b> — click to expand</summary>

| Step | Action |
|------|--------|
| 1 | Checks prerequisites (git, docker, docker compose) |
| 2 | Clones the repo (`--depth 1`) |
| 3 | Copies `.env.example` → `.env` |
| 4 | Pulls Docker images |
| 5 | Runs `docker compose up -d` |

> **Prerequisites**: git · docker · docker compose
</details>

---

## 🏗️ Architecture

```mermaid
flowchart TB
    User([User Prompt]) --> Orch[Orchestrator<br/>LangGraph State Machine]
    
    subgraph Agents[" "]
        Dev[DevAgent<br/>Code · CI/CD · Deploy]
        Content[ContentAgent<br/>SEO · Images · CMS]
        Marketing[MarketingAgent<br/>Email · Ads · Analytics]
        Commerce[CommerceAgent<br/>Catalog · Checkout · FAQ]
    end
    
    Orch --> Agents
    
    subgraph Memory[" "]
        PG[(PostgreSQL<br/>+ pgvector)]
        RC[(Redis Cache)]
    end
    
    Agents --> Memory
    Agents --> HITL{HITL<br/>Human Approval}
    HITL -->|Approved| Output[Deploy / Publish / Charge]
    HITL -->|Rejected| Log[Audit Log]
    Output --> Log
```

<details>
<summary><b>📦 Services</b></summary>

| Container | Role | Port |
|-----------|------|------|
| `postgres` | PostgreSQL 17 + pgvector | 5432 |
| `redis` | Redis 7 + AOF persistence | 6379 |
| `ollama` | Local LLM fallback (qwen2.5) | 11434 |
| `mailhog` | SMTP email preview | 1025 · 8025 |
| `strapi` | Headless CMS | 1337 |
| `jaeger` | Distributed tracing (OTLP) | 16686 · 4318 |
| `minio` | S3-compatible object storage | 9000 · 9001 |
| `caddy` | TLS reverse proxy | 80 · 443 |
| `app` | FastAPI orchestrator | 8000 |
| `web` | Next.js dashboard | 3000 |

</details>

---

## 🎯 Agents

<table>
<tr>
  <td width="25%" align="center">
    <h3>💻 DevAgent</h3>
    <span style="background:#e7f5ff;color:#1971c2;padding:2px 8px;border-radius:4px;font-size:12px">code</span>
    <p>Scaffold repos · CI/CD · Tests · Deploy</p>
    <small>🔧 GitHub API · Docker · pytest</small>
  </td>
  <td width="25%" align="center">
    <h3>📝 ContentAgent</h3>
    <span style="background:#f3f0ff;color:#7048e8;padding:2px 8px;border-radius:4px;font-size:12px">content</span>
    <p>SEO copy · Images · CMS · Calendar</p>
    <small>✍️ GPT-4o · Replicate · Strapi</small>
  </td>
  <td width="25%" align="center">
    <h3>📊 MarketingAgent</h3>
    <span style="background:#fff0f6;color:#c2255c;padding:2px 8px;border-radius:4px;font-size:12px">growth</span>
    <p>Segments · Campaigns · Ads · Reports</p>
    <small>📧 SMTP · Meta/Google · GA4</small>
  </td>
  <td width="25%" align="center">
    <h3>💰 CommerceAgent</h3>
    <span style="background:#ebfbee;color:#2b8a3e;padding:2px 8px;border-radius:4px;font-size:12px">sales</span>
    <p>Catalog · Pricing · Stripe · FAQ</p>
    <small>💳 Stripe · Redis · LangChain</small>
  </td>
</tr>
</table>

### 🔄 Pipeline Flow

```
User Prompt → Orchestrator decomposes → Dev (code) → Content (create) → Marketing (launch) → Commerce (sell)
                                                                                          ↓
                                                                                    HITL validation
                                                                                          ↓
                                                                                    Deploy / Publish / Charge
```

---

## ⚡ Features

| | Feature | Description |
|---|---------|-------------|
| 🧠 | **4 Specialized Agents** | Dev, Content, Marketing, Commerce — each with domain-specific tools |
| 👤 | **Human-in-the-Loop** | Deploy, publish, charge actions require your approval |
| 🔄 | **LLM Fallback** | OpenRouter → Ollama local → degraded response |
| 🧩 | **Vector Memory** | PostgreSQL + pgvector (768d embeddings) for project context |
| ⚡ | **Redis Cache** | Tiered TTL: 60s LLM · 3600s sessions · 86400s projects |
| ⛔ | **Circuit Breaker** | Auto-disables agents after 3 consecutive failures |
| 📋 | **JSON Logging** | Immutable structured logs with secret masking |
| 🏖️ | **Docker Sandbox** | Isolated execution, filtered network, resource limits |
| 🎯 | **Configurable Priority** | Task priority system (0–10) |
| 📦 | **1-Click Deploy** | `docker compose up` — full stack in one command |
| ⚡ | **Parallel Execution** | Independent agents run concurrently via asyncio.gather |
| 🔄 | **Multi-Model Routing** | Claude for code, GPT-4o for content, Mixtral for analysis |
| 💾 | **LLM Response Cache** | In-memory SHA256-keyed cache reduces API costs |
| 📡 | **WebSocket Logs** | Real-time log streaming at `/ws/logs` |
| 📊 | **Prometheus Metrics** | `/metrics` endpoint for counters, histograms, gauges |
| 🔍 | **Distributed Tracing** | OpenTelemetry spans exported to Jaeger |
| 🔔 | **Notifications** | Slack + Console multi-channel broadcasts |
| 🗓️ | **Scheduler** | Cron-based periodic task execution |
| 🏢 | **Workspaces** | Multi-tenant project isolation |

<details>
<summary><b>🔒 Security & Compliance</b></summary>

- Secrets in `.env` only — never in code
- Partial secret masking in logs (tokens masked)
- Sandbox with filtered network access
- JWT/session-based auth for dashboard
- Audit trail via immutable JSON logs
</details>

---

## 📖 Quick Start

### 1️⃣ Configure

```bash
cp .env.example .env
# Edit .env with your API keys (or use defaults for local-only mode)
```

### 2️⃣ Launch

```bash
docker compose up -d
```

<details>
<summary><b>⏳ Wait for health checks</b></summary>

```bash
watch docker compose ps  # Wait until all services are "healthy"
```
</details>

### 3️⃣ Verify

```bash
curl http://localhost:8000/health
# → {"status":"ok","version":"3.0.0","environment":"development"}
```

### 4️⃣ Run a workflow

```bash
curl -X POST http://localhost:8000/api/v1/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Create a landing page for a SaaS product"}'
```

---

## 🎮 Makefile Commands

<table>
<tr><th>Command</th><th>Description</th></tr>
<tr><td><code>make up</code></td><td>Start all services</td></tr>
<tr><td><code>make down</code></td><td>Stop all services</td></tr>
<tr><td><code>make logs</code></td><td>Follow logs</td></tr>
<tr><td><code>make test</code></td><td>Run pytest with coverage</td></tr>
<tr><td><code>make lint</code></td><td>Run ruff + mypy</td></tr>
<tr><td><code>make shell</code></td><td>Open app container shell</td></tr>
<tr><td><code>make seed</code></td><td>Seed database</td></tr>
<tr><td><code>make clean</code></td><td>Clean volumes</td></tr>
<tr><td><code>make reset</code></td><td>Full reset (down → clean → up)</td></tr>
<tr><td><code>make backup</code></td><td>Backup PostgreSQL</td></tr>
</table>

---

## 📡 API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/health/full` | GET | Full health (DB, Redis, Ollama) |
| `/metrics` | GET | Prometheus metrics |
| `/ws/logs` | WS | Real-time log stream |
| `/api/v1/run` | POST | Execute a workflow |
| `/api/v1/status/{session_id}` | GET | Get workflow status |
| `/api/v1/trace/{session_id}` | GET | Trace spans for a workflow |
| `/api/v1/hitl/approve` | POST | Approve a pending action |
| `/api/v1/hitl/reject` | POST | Reject a pending action |
| `/api/v1/hitl/pending` | GET | List pending approvals |
| `/api/v1/scheduler/create` | POST | Create a scheduled task |
| `/api/v1/scheduler/list` | GET | List scheduled tasks |
| `/api/v1/workspaces` | GET | List workspaces |
| `/api/v1/project/export` | POST | Export project data |
| `/api/v1/project/import` | POST | Import project data |
| `/api/v1/llm/cache/clear` | POST | Clear LLM response cache |
| `/api/v1/notify/test` | POST | Test notification channel |
| `/docs` | GET | Swagger UI |

<details>
<summary><b>📝 Example: Submit & approve</b></summary>

```bash
# Submit workflow
WORKFLOW=$(curl -s -X POST http://localhost:8000/api/v1/run \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Deploy my app to staging"}')

# Get session ID from response
SESSION_ID=$(echo $WORKFLOW | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)

# List pending HITL
PENDING=$(curl -s http://localhost:8000/api/v1/hitl/pending)
APPROVAL_ID=$(echo $PENDING | grep -o '"id":"[^"]*"' | cut -d'"' -f4 | head -1)

# Approve
curl -X POST http://localhost:8000/api/v1/hitl/approve \
  -H "Content-Type: application/json" \
  -d "{\"approval_id\":\"$APPROVAL_ID\"}"
```
</details>

---

## 🌐 Dashboard

Open **[http://localhost:3000](http://localhost:3000)** in your browser.

```
┌─────────────────────────────────────────────┐
│  AgentOS Dashboard                          │
├──────────────────┬──────────────────────────┤
│  Run Workflow    │  Pending Approvals       │
│  ┌──────────────┐│  ┌──────────────────────┐│
│  │ Describe...  ││  │ DevAgent: deploy    ││
│  └──────────────┘│  │ [Approve] [Reject]  ││
│  [▶ Run]         │  └──────────────────────┘│
├──────────────────┼──────────────────────────┤
│  Agent Results   │  System Status           │
│  ✓ DevAgent OK   │  ● API · ● DB · ● Redis │
│  ⏳ Content...   │  ● Ollama · ● Strapi    │
└──────────────────┴──────────────────────────┘
```

**Login**: `admin@agentos.local` / `agentos`

---

## 🗂️ Project Structure

<details>
<summary><b>Click to expand</b></summary>

```
agentos/
├── docker-compose.yml     # 7 services: postgres, redis, ollama, mailhog, strapi, app, web
├── Dockerfile             # Python 3.13 app container
├── Makefile               # 12 automation commands
├── .env.example           # 30+ env vars with demo defaults
├── install.sh             # One-liner curl installer
├── docs/                  # GitHub Pages landing page
└── app/
    ├── main.py            # FastAPI entrypoint with all routes
    ├── orchestrator.py    # LangGraph state machine (retry×3, circuit breaker)
    ├── agents/
    │   ├── base.py        # Abstract agent with HITL, LLM fallback
    │   ├── dev.py         # scaffold, test, lint, deploy
    │   ├── content.py     # write, image, calendar, publish
    │   ├── marketing.py   # segment, email, ads, report
    │   └── commerce.py    # catalog, pricing, checkout, inventory, faq
    ├── memory/
    │   ├── vector_store.py # pgvector 768d + JSON fallback
    │   ├── cache.py        # Redis + local dict fallback
    │   └── session.py      # Session persistence + fallback
    ├── config/
    │   ├── settings.py     # Pydantic Settings
    │   ├── policies.yaml   # Security + orchestration policies
    │   └── prompts.yaml    # System prompts per agent
    ├── utils/
    │   ├── logging.py      # JSON immutable logs + secret masking
    │   ├── api_clients.py  # OpenRouter + Ollama + degraded
    │   ├── hitl_gateway.py # Webhook + CLI approval
    │   └── sandbox.py      # Docker container isolation
    ├── tests/
    │   ├── conftest.py     # Fixtures, mocks, async client
    │   ├── test_orchestrator.py
    │   ├── test_hitl.py
    │   └── test_memory.py
    └── web/                # Next.js 14 App Router dashboard
        ├── app/            # Pages, layouts, components
        └── Dockerfile.web  # Standalone container
```
</details>

---

## 🧪 Testing

```bash
# Full test suite with coverage
make test

# Run specific tests
docker compose exec app python -m pytest app/tests/test_hitl.py -v

# Lint
make lint
```

| Metric | Target |
|--------|--------|
| Coverage | ≥ 90% |
| Tests | 18+ (orchestration, HITL, memory) |
| Type checks | mypy strict |

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/amazing`)
3. Commit (`git commit -m 'Add amazing feature'`)
4. Push (`git push origin feature/amazing`)
5. Open a Pull Request

---

## 📊 Status

| Service | Status |
|---------|--------|
| CI/CD | [![Build](https://github.com/HiTechTN/agentos/actions/workflows/docker.yml/badge.svg)](https://github.com/HiTechTN/agentos/actions/workflows/docker.yml) |
| Docker App | `ghcr.io/hitechtn/agentos:latest` |
| Docker Web | `ghcr.io/hitechtn/agentos/web:latest` |
| Landing | [hitechtn.github.io/agentos](https://hitechtn.github.io/agentos/) |
| License | [MIT](LICENSE) |

---

<p align="center">
  <b>Built with</b>
  <br>
  <img src="https://img.shields.io/badge/Python_3.13-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/LangGraph-FF6F00?logo=langchain&logoColor=white" alt="LangGraph">
  <img src="https://img.shields.io/badge/PostgreSQL_17-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Redis-FF4438?logo=redis&logoColor=white" alt="Redis">
  <img src="https://img.shields.io/badge/OpenRouter-FF6B6B?logo=openai&logoColor=white" alt="OpenRouter">
  <img src="https://img.shields.io/badge/Next.js_14-000000?logo=next.js&logoColor=white" alt="Next.js">
  <img src="https://img.shields.io/badge/Docker_Compose-2496ED?logo=docker&logoColor=white" alt="Docker">
  <br><br>
  <a href="https://github.com/HiTechTN/agentos">📦 GitHub</a> ·
  <a href="https://hitechtn.github.io/agentos/">🌐 Landing Page</a> ·
  <a href="https://github.com/HiTechTN/agentos/releases">📝 Releases</a>
</p>
