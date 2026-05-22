# AgentOS — Dossier de Mise à Niveau Professionnelle
## Instruments structurés pour l'agent codeur · v4.0 → v5.0

> **Scope** : Audit complet + roadmap d'upgrade + AGENTS.md étendu + patterns de code + checklist de validation  
> **Cible** : Agent codeur autonome (Claude Code / Continue.dev / Cursor)  
> **Stack actuelle** : Python 3.13 · FastAPI · LangGraph · PostgreSQL + pgvector · Redis · Next.js 14 · Docker Compose

---

## 0. SYNTHÈSE D'AUDIT — État actuel v4.0

### ✅ Points forts identifiés
- Architecture multi-agent solide : Orchestrator LangGraph + 4 domain agents + 4 sub-agents
- Infrastructure complète : 10 services Docker Compose (postgres, redis, ollama, jaeger, minio, caddy…)
- Observabilité : Prometheus + Jaeger OTLP + WebSocket logs
- Sécurité de base : sandbox Docker, secret masking, HITL gate
- Test coverage cible ≥ 90% avec 77+ tests pytest
- LLM fallback chain : OpenRouter → Ollama → degraded response

### ❌ Gaps critiques identifiés
| # | Problème | Sévérité | Fichier/Zone |
|---|----------|----------|--------------|
| G1 | `requirements.txt` non pinné (versions flottantes `>=`) | HIGH | `requirements.txt` |
| G2 | Pas de `uv` / `uv.lock` — reproductibilité cassée | HIGH | racine |
| G3 | Absence de `alembic` pour migrations DB | HIGH | `app/` |
| G4 | `docker-compose.yml` sans `healthcheck` sur tous les services | MEDIUM | infrastructure |
| G5 | Pas de rate limiting sur l'API FastAPI | HIGH | `app/main.py` |
| G6 | JWT auth non documentée / endpoints non protégés | HIGH | `app/main.py` |
| G7 | LLM cache SHA256 en mémoire uniquement — perdu au restart | MEDIUM | `app/utils/api_clients.py` |
| G8 | `AGENTS.md` incomplet — règles de sub-agents non formalisées | MEDIUM | `AGENTS.md` |
| G9 | Next.js dashboard non typé (TypeScript partiel 8.1%) | MEDIUM | `app/web/` |
| G10 | CI/CD uniquement Docker build — pas de tests, lint, security scan | HIGH | `.github/workflows/` |

---

## 1. AGENTS.md — RÈGLES ÉTENDUES (v5.0)

> Copier ce fichier à la racine du projet sous `AGENTS.md`

```markdown
# AGENTS.md — AgentOS Project Rules v5.0
# Auto-loaded by @Planner, @Verifier, @Explorer, @CodeReviewer

## GLOBAL RULES (s'appliquent à tous les agents)

### Code Quality
- TOUJOURS utiliser des type hints Python complets (mypy strict)
- TOUJOURS écrire des docstrings Google-style sur toutes les classes/fonctions publiques
- JAMAIS de `Any` dans les signatures publiques sans justification dans le docstring
- Longueur max de fonction : 50 lignes. Refactoriser si dépassé.
- Longueur max de fichier : 300 lignes. Splitter en modules si dépassé.
- TOUJOURS utiliser `async`/`await` pour les opérations I/O

### Dependency Management
- Utiliser `uv` pour toutes les opérations de packages
- `uv add <pkg>` pour ajouter, `uv remove <pkg>` pour retirer
- JAMAIS modifier `requirements.txt` directement — généré par `uv export`
- Versions TOUJOURS épinglées dans `pyproject.toml` sous `[tool.uv.constraints]`

### Database
- TOUJOURS créer une migration Alembic pour tout changement de schéma
- `alembic revision --autogenerate -m "description_courte"`
- JAMAIS de `CREATE TABLE` en raw SQL dans le code applicatif
- Nommer les migrations : `YYYYMMDD_HHMMSS_description.py`

### Security
- JAMAIS logger des secrets, tokens, passwords
- TOUJOURS valider les inputs avec Pydantic v2 `model_validator`
- TOUJOURS utiliser `SecretStr` de Pydantic pour les champs sensibles
- Rate limiting obligatoire sur tous les endpoints POST/PUT/DELETE
- Auth JWT obligatoire sur tous les endpoints sauf `/health` et `/metrics`

### Testing
- TOUJOURS écrire le test AVANT le code (TDD)
- Coverage minimum : 90% par module
- Nommer les tests : `test_<unit>_<scenario>_<expected_outcome>`
- Utiliser des fixtures pytest, jamais de setup dans les test functions
- Mocker les LLM calls avec `pytest-httpx`

### Git
- Commits conventionnels : `type(scope): description`
  - Types : feat, fix, docs, test, refactor, chore, perf, security
  - Exemples : `feat(agents): add @Debugger sub-agent`
  - Exemples : `fix(memory): persist LLM cache to Redis on shutdown`
- JAMAIS committer `.env`, `*.key`, `*.pem`
- TOUJOURS créer une branche feature depuis `main`

---

## @PLANNER RULES

### Structured Plan Output (OBLIGATOIRE)
Chaque plan doit contenir :
```json
{
  "goal": "string",
  "phases": [
    {
      "id": "P1",
      "name": "string",
      "duration_estimate": "Xh",
      "tasks": [
        {
          "id": "T1.1",
          "title": "string",
          "agent": "@DevAgent | @ContentAgent | ...",
          "depends_on": ["T1.0"],
          "acceptance_criteria": ["criterion1"],
          "risks": ["risk1"]
        }
      ]
    }
  ],
  "architecture_decisions": [],
  "dependencies": {},
  "total_estimate": "Xh"
}
```

### Planning Constraints
- Maximum 5 phases par plan
- Maximum 8 tâches par phase
- TOUJOURS identifier les dépendances circulaires avant dispatch
- TOUJOURS inclure une phase "P0: Setup & Prerequisites"
- TOUJOURS inclure une phase finale "PN: Validation & Cleanup"

---

## @VERIFIER RULES

### Validation Pipeline (dans l'ordre)
1. `ruff check app/ --fix` — lint auto-fix
2. `ruff format app/` — formatting
3. `mypy app/ --strict` — type checking (0 erreurs requis)
4. `pytest app/tests/ --cov=app --cov-fail-under=90` — tests
5. `bandit -r app/ -ll` — security scan
6. `docker compose config` — validate compose file

### Issue Format (JSON obligatoire)
```json
{
  "issues": [
    {
      "id": "V001",
      "severity": "error|warning|info",
      "file": "app/agents/dev.py",
      "line": 42,
      "rule": "mypy:arg-type",
      "message": "description",
      "suggestion": "fix code here"
    }
  ],
  "summary": { "errors": 0, "warnings": 2, "info": 5 },
  "passed": true
}
```

---

## @EXPLORER RULES

### Search Strategy
- Toujours commencer par `grep -r "pattern" app/ --include="*.py" -n`
- Cartographier les imports avant de modifier un module
- Identifier tous les callers d'une fonction avant de la modifier
- Utiliser `ast` pour analyser la structure sans exécuter

### Dependency Map Format
```
module: app.agents.dev
  imports: [app.agents.base, app.memory.vector_store, app.utils.api_clients]
  imported_by: [app.orchestrator, app.main]
  exports: [DevAgent, DevTask]
```

---

## @CODEREREVIEWER RULES

### Review Checklist (MANDATORY)
- [ ] Pas de secrets hardcodés (regex: `(?i)(key|token|secret|password)\s*=\s*["'][^"']+["']`)
- [ ] Pas de SQL injection (f-strings dans les queries)
- [ ] Pas de path traversal (user input dans os.path)
- [ ] Type hints complets
- [ ] Error handling avec exceptions typées
- [ ] Logs structurés (pas de print())
- [ ] Resource cleanup (context managers, finally blocks)
- [ ] Async correctness (pas de blocking I/O dans coroutines)

### Security Severity
- CRITICAL: secrets exposés, injection, RCE possible
- HIGH: auth bypass, IDOR, path traversal
- MEDIUM: missing rate limit, verbose errors, weak crypto
- LOW: missing logs, style, docs

---

## PROJECT RULES

### Module Responsibilities (NE PAS CROISER)
- `app/agents/` → logique métier des agents uniquement
- `app/workflow/` → orchestration de flux (plan/verify)
- `app/memory/` → persistance et retrieval uniquement
- `app/utils/` → utilitaires transverses sans logique métier
- `app/config/` → configuration et settings uniquement
- `app/mcp/` → intégration MCP protocol uniquement

### API Conventions
- Tous les endpoints retournent `{"data": ..., "meta": {...}, "errors": []}`
- Status codes : 200 OK, 201 Created, 202 Accepted (async), 400 Bad Request, 401 Unauthorized, 422 Validation Error, 429 Rate Limit, 500 Internal
- Versioning : `/api/v1/` pour stable, `/api/v2/` pour beta
- Pagination : `?page=1&per_page=20` avec `meta.total`, `meta.pages`

### Performance Targets
- Endpoint `/api/v1/run` : p95 < 500ms (hors LLM)
- Endpoint `/api/v1/plan` : p95 < 200ms
- WebSocket `/ws/logs` : latence < 50ms
- DB queries : p99 < 100ms (index obligatoire sur FK et colonnes filtrées)
```

---

## 2. UPGRADES CRITIQUES — CODE PATTERNS

### 2.1 Dependency Management → `uv` + versions épinglées

```toml
# pyproject.toml (remplacer requirements.txt)
[project]
name = "agentos"
version = "5.0.0"
requires-python = ">=3.13"
dependencies = [
    "fastapi==0.115.6",
    "uvicorn[standard]==0.32.1",
    "langgraph==0.3.18",
    "langchain-core==0.3.29",
    "pydantic==2.10.4",
    "pydantic-settings==2.6.1",
    "asyncpg==0.30.0",
    "sqlalchemy[asyncio]==2.0.36",
    "pgvector==0.3.6",
    "redis[hiredis]==5.2.1",
    "httpx==0.28.1",
    "pyyaml==6.0.2",
    "rich==13.9.4",
    "python-dotenv==1.0.1",
    "pyjwt==2.9.0",
    "openai==1.58.1",
    "docker==7.1.0",
    "python-multipart==0.0.20",
    "opentelemetry-api==1.29.0",
    "opentelemetry-sdk==1.29.0",
    "opentelemetry-exporter-otlp==1.29.0",
    "alembic==1.14.0",
    "slowapi==0.1.9",
    "bandit==1.8.0",
    "replicate==0.34.2",
]

[tool.uv.constraints]
# Freeze transitive deps via: uv lock && uv export > requirements.txt
```

### 2.2 Alembic — Migration Setup

```bash
# Initialisation (une seule fois)
uv run alembic init app/migrations

# Modifier app/migrations/env.py :
# from app.config.settings import settings
# config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Créer la première migration baseline
uv run alembic revision --autogenerate -m "baseline_v5"
uv run alembic upgrade head
```

```python
# app/migrations/versions/20260522_000000_baseline_v5.py
"""baseline_v5

Revision ID: 001
Revises: 
Create Date: 2026-05-22
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        'sessions',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', sa.String(64), nullable=False, index=True),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('status', sa.String(32), nullable=False, server_default='pending'),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_table(
        'embeddings',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('session_id', sa.UUID(), sa.ForeignKey('sessions.id', ondelete='CASCADE')),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(768), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.execute("CREATE INDEX ON embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")

def downgrade() -> None:
    op.drop_table('embeddings')
    op.drop_table('sessions')
```

### 2.3 Rate Limiting — `slowapi`

```python
# app/utils/rate_limit.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],
    storage_uri="redis://redis:6379/1",  # Persist en Redis
)

# Limites spécifiques par endpoint
LIMITS = {
    "run": "10/minute",       # Workflow execution — coûteux
    "plan": "20/minute",      # Plan creation
    "verify": "30/minute",    # Verification
    "sub_agent": "15/minute", # Sub-agent calls
}

# app/main.py — ajouter dans lifespan :
# app.state.limiter = limiter
# app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Usage sur un endpoint :
# @router.post("/run")
# @limiter.limit(LIMITS["run"])
# async def run_workflow(request: Request, body: RunRequest):
#     ...
```

### 2.4 Auth Middleware — JWT obligatoire

```python
# app/utils/auth.py
from __future__ import annotations
import jwt
from datetime import datetime, timedelta, timezone
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from app.config.settings import settings

bearer_scheme = HTTPBearer(auto_error=False)

class TokenPayload(BaseModel):
    sub: str          # user_id
    workspace: str    # workspace_id
    exp: datetime
    role: str = "user"  # "user" | "admin"

def create_access_token(sub: str, workspace: str, role: str = "user") -> str:
    payload = {
        "sub": sub,
        "workspace": workspace,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET.get_secret_value(), algorithm="HS256")

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> TokenPayload:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET.get_secret_value(),
            algorithms=["HS256"],
        )
        return TokenPayload(**payload)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

# Dépendance admin uniquement
async def require_admin(user: Annotated[TokenPayload, Depends(get_current_user)]) -> TokenPayload:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return user

CurrentUser = Annotated[TokenPayload, Depends(get_current_user)]
AdminUser = Annotated[TokenPayload, Depends(require_admin)]
```

### 2.5 LLM Cache — Persistance Redis

```python
# app/utils/llm_cache.py — Remplacer le cache in-memory
import hashlib, json
from typing import Any
import redis.asyncio as redis_async
from app.config.settings import settings

class PersistentLLMCache:
    """SHA256-keyed LLM response cache with Redis backend + local L1."""

    def __init__(self) -> None:
        self._l1: dict[str, Any] = {}  # In-memory L1
        self._redis: redis_async.Redis | None = None
        self.TTL_SECONDS = 86400 * 7   # 7 jours

    async def connect(self) -> None:
        self._redis = redis_async.from_url(
            settings.REDIS_URL, encoding="utf-8", decode_responses=True
        )

    def _key(self, model: str, messages: list[dict]) -> str:
        payload = json.dumps({"model": model, "messages": messages}, sort_keys=True)
        return f"llm_cache:{hashlib.sha256(payload.encode()).hexdigest()}"

    async def get(self, model: str, messages: list[dict]) -> Any | None:
        key = self._key(model, messages)
        if key in self._l1:
            return self._l1[key]
        if self._redis:
            raw = await self._redis.get(key)
            if raw:
                value = json.loads(raw)
                self._l1[key] = value  # Promote to L1
                return value
        return None

    async def set(self, model: str, messages: list[dict], response: Any) -> None:
        key = self._key(model, messages)
        self._l1[key] = response
        if self._redis:
            await self._redis.setex(key, self.TTL_SECONDS, json.dumps(response))

    async def invalidate_pattern(self, pattern: str = "llm_cache:*") -> int:
        """Flush cache entries matching pattern."""
        if not self._redis:
            return 0
        keys = await self._redis.keys(pattern)
        if keys:
            return await self._redis.delete(*keys)
        return 0

llm_cache = PersistentLLMCache()
```

### 2.6 Structured Response — Pydantic v2

```python
# app/schemas/responses.py — Format API unifié
from __future__ import annotations
from typing import Generic, TypeVar, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone

T = TypeVar("T")

class Meta(BaseModel):
    request_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "5.0.0"
    pagination: PaginationMeta | None = None

class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int
    pages: int

class APIError(BaseModel):
    code: str
    message: str
    field: str | None = None
    details: dict[str, Any] | None = None

class APIResponse(BaseModel, Generic[T]):
    data: T | None = None
    meta: Meta
    errors: list[APIError] = Field(default_factory=list)

    @classmethod
    def ok(cls, data: T, request_id: str, **meta_kwargs) -> "APIResponse[T]":
        return cls(data=data, meta=Meta(request_id=request_id, **meta_kwargs))

    @classmethod
    def fail(cls, errors: list[APIError], request_id: str) -> "APIResponse[None]":
        return cls(data=None, meta=Meta(request_id=request_id), errors=errors)

# Usage dans un endpoint :
# @router.post("/run", response_model=APIResponse[WorkflowStatus])
# async def run(body: RunRequest, request: Request, user: CurrentUser):
#     result = await orchestrator.run(body.prompt, user.workspace)
#     return APIResponse.ok(result, request_id=request.state.request_id)
```

### 2.7 @Debugger Sub-Agent (nouveau)

```python
# app/agents/sub_agents/debugger.py
"""@Debugger — Analyse d'erreurs runtime et proposition de fixes."""
from __future__ import annotations
import traceback
from pydantic import BaseModel
from app.agents.base import BaseAgent
from app.utils.api_clients import llm_client

class DebugContext(BaseModel):
    error_type: str
    error_message: str
    traceback: str
    file: str | None = None
    line: int | None = None
    code_snippet: str | None = None

class DebugResult(BaseModel):
    root_cause: str
    explanation: str
    fix_suggestion: str
    code_patch: str | None = None
    related_files: list[str] = []
    confidence: float  # 0.0 - 1.0

DEBUGGER_PROMPT = """Tu es @Debugger, un expert en débogage Python/FastAPI/LangGraph.
Analyse l'erreur fournie et retourne un JSON avec :
- root_cause : cause racine en 1 phrase
- explanation : explication technique détaillée
- fix_suggestion : correction recommandée
- code_patch : code corrigé si applicable (diff unifié)
- related_files : fichiers potentiellement impactés
- confidence : score de confiance 0.0-1.0

Contexte projet : FastAPI + LangGraph + PostgreSQL + Redis.
RÉPONDRE UNIQUEMENT EN JSON, sans markdown.
"""

class DebuggerAgent(BaseAgent):
    name = "@Debugger"
    triggers = ["error", "exception", "traceback", "debug", "fix", "crash"]

    async def run(self, context: DebugContext) -> DebugResult:
        prompt = f"Erreur à analyser:\n{context.model_dump_json(indent=2)}"
        response = await llm_client.complete(
            model="claude-sonnet-4-20250514",
            system=DEBUGGER_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return DebugResult.model_validate_json(response.content)

    @classmethod
    def from_exception(cls, exc: Exception) -> DebugContext:
        tb = traceback.extract_tb(exc.__traceback__)
        last_frame = tb[-1] if tb else None
        return DebugContext(
            error_type=type(exc).__name__,
            error_message=str(exc),
            traceback=traceback.format_exc(),
            file=last_frame.filename if last_frame else None,
            line=last_frame.lineno if last_frame else None,
        )
```

---

## 3. CI/CD — PIPELINE COMPLET v5.0

```yaml
# .github/workflows/ci.yml — REMPLACER docker.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}
  PYTHON_VERSION: "3.13"

jobs:
  # ─── 1. Code Quality ────────────────────────────────────────────
  lint:
    name: Lint & Type Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
        with: { version: "latest" }
      - run: uv sync --frozen
      - run: uv run ruff check app/ --output-format=github
      - run: uv run ruff format app/ --check
      - run: uv run mypy app/ --strict --no-error-summary
      
  security:
    name: Security Scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --frozen
      - run: uv run bandit -r app/ -ll -f json -o bandit-report.json
      - run: uv run pip-audit --fix --dry-run  # Check for CVEs
      - uses: actions/upload-artifact@v4
        with: { name: security-report, path: bandit-report.json }

  # ─── 2. Tests ───────────────────────────────────────────────────
  test:
    name: Tests (Python ${{ matrix.python-version }})
    runs-on: ubuntu-latest
    needs: [lint]
    strategy:
      matrix:
        python-version: ["3.12", "3.13"]
    services:
      postgres:
        image: pgvector/pgvector:pg17
        env:
          POSTGRES_DB: agentos_test
          POSTGRES_USER: agentos
          POSTGRES_PASSWORD: agentos
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --frozen
      - name: Run migrations
        env:
          DATABASE_URL: postgresql+asyncpg://agentos:agentos@localhost/agentos_test
        run: uv run alembic upgrade head
      - name: Run tests
        env:
          DATABASE_URL: postgresql+asyncpg://agentos:agentos@localhost/agentos_test
          REDIS_URL: redis://localhost:6379/0
          ENVIRONMENT: test
        run: |
          uv run pytest app/tests/ \
            --cov=app \
            --cov-report=xml \
            --cov-report=term-missing \
            --cov-fail-under=90 \
            -v \
            --tb=short
      - uses: codecov/codecov-action@v4
        with: { files: coverage.xml }

  # ─── 3. Docker Build & Push ─────────────────────────────────────
  docker:
    name: Docker Build
    runs-on: ubuntu-latest
    needs: [test, security]
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        with:
          context: .
          push: ${{ github.ref == 'refs/heads/main' }}
          tags: |
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:latest
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          build-args: |
            BUILDKIT_INLINE_CACHE=1

  # ─── 4. Deploy (main branch only) ───────────────────────────────
  deploy:
    name: Deploy to Production
    runs-on: ubuntu-latest
    needs: [docker]
    if: github.ref == 'refs/heads/main'
    environment: production
    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.DEPLOY_HOST }}
          username: ${{ secrets.DEPLOY_USER }}
          key: ${{ secrets.DEPLOY_KEY }}
          script: |
            cd /opt/agentos
            docker compose pull
            docker compose up -d --remove-orphans
            docker system prune -f
```

---

## 4. DOCKERFILE — OPTIMISATION MULTI-STAGE

```dockerfile
# Dockerfile v5.0 — Multi-stage, non-root, uv-based

# ─── Stage 1: Builder ─────────────────────────────────────────────
FROM python:3.13-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Dependencies first (cache layer)
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Copy source
COPY app/ ./app/

# ─── Stage 2: Runtime ─────────────────────────────────────────────
FROM python:3.13-slim AS runtime

# Security: non-root user
RUN groupadd --gid 1001 agentos && \
    useradd --uid 1001 --gid agentos --shell /bin/bash --create-home agentos

WORKDIR /app

# Copy deps from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app ./app

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

USER agentos

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "4", "--access-log", "--log-level", "info"]
```

---

## 5. NOUVEAUX MODULES À CRÉER (v5.0)

### 5.1 `app/agents/sub_agents/debugger.py`
→ Voir section 2.7

### 5.2 `app/utils/request_id.py` — Middleware Request ID

```python
# app/utils/request_id.py
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

### 5.3 `app/utils/health.py` — Health Check détaillé

```python
# app/utils/health.py
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel
import asyncpg, redis.asyncio as aioredis, httpx
from app.config.settings import settings

HealthStatus = Literal["ok", "degraded", "down"]

class ServiceHealth(BaseModel):
    status: HealthStatus
    latency_ms: float | None = None
    error: str | None = None

class FullHealthReport(BaseModel):
    status: HealthStatus
    version: str = "5.0.0"
    environment: str
    services: dict[str, ServiceHealth]

async def check_postgres() -> ServiceHealth:
    import time
    try:
        t0 = time.monotonic()
        conn = await asyncpg.connect(settings.DATABASE_URL.replace("+asyncpg", ""))
        await conn.fetchval("SELECT 1")
        await conn.close()
        return ServiceHealth(status="ok", latency_ms=(time.monotonic() - t0) * 1000)
    except Exception as e:
        return ServiceHealth(status="down", error=str(e))

async def check_redis() -> ServiceHealth:
    import time
    try:
        t0 = time.monotonic()
        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.aclose()
        return ServiceHealth(status="ok", latency_ms=(time.monotonic() - t0) * 1000)
    except Exception as e:
        return ServiceHealth(status="down", error=str(e))

async def check_ollama() -> ServiceHealth:
    import time
    try:
        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            r.raise_for_status()
        return ServiceHealth(status="ok", latency_ms=(time.monotonic() - t0) * 1000)
    except Exception as e:
        return ServiceHealth(status="degraded", error=str(e))

async def full_health_check() -> FullHealthReport:
    import asyncio
    pg, rd, ol = await asyncio.gather(check_postgres(), check_redis(), check_ollama())
    services = {"postgres": pg, "redis": rd, "ollama": ol}
    overall: HealthStatus = "ok"
    if any(s.status == "down" for s in [pg, rd]):
        overall = "down"
    elif any(s.status == "degraded" for s in services.values()):
        overall = "degraded"
    return FullHealthReport(
        status=overall,
        environment=settings.ENVIRONMENT,
        services=services,
    )
```

---

## 6. CHECKLIST DE VALIDATION — v5.0 READY

> L'agent codeur doit cocher chaque item avant de marquer v5.0 comme DONE.

### Infrastructure
- [ ] `uv.lock` committé avec toutes les dépendances épinglées
- [ ] `pyproject.toml` remplace `requirements.txt` (garder `requirements.txt` généré pour compat)
- [ ] `alembic.ini` configuré + première migration baseline créée
- [ ] `docker-compose.yml` : healthcheck sur TOUS les services
- [ ] `.env.example` mis à jour avec les nouvelles variables (JWT_SECRET, etc.)
- [ ] Dockerfile multi-stage + user non-root validé

### Sécurité
- [ ] `slowapi` rate limiting actif sur tous les POST/PUT/DELETE
- [ ] JWT middleware sur tous les endpoints sauf `/health`, `/metrics`, `/docs`
- [ ] `bandit` passe sans issues MEDIUM+ (`bandit -r app/ -ll`)
- [ ] `pip-audit` : 0 CVE critique
- [ ] `.dockerignore` exclut `.env`, `*.key`, `__pycache__`

### Qualité de code
- [ ] `mypy app/ --strict` → 0 erreurs
- [ ] `ruff check app/` → 0 erreurs
- [ ] Coverage ≥ 90% (`pytest --cov-fail-under=90`)
- [ ] Tous les endpoints retournent `APIResponse[T]`
- [ ] Request ID tracé dans tous les logs

### Tests
- [ ] Tests pour `rate_limit.py`
- [ ] Tests pour `auth.py` (valid/expired/missing token)
- [ ] Tests pour `llm_cache.py` (L1 hit, Redis hit, miss)
- [ ] Tests pour `@Debugger` sub-agent
- [ ] Tests d'intégration avec la base de données de test

### CI/CD
- [ ] Pipeline `ci.yml` remplace `docker.yml`
- [ ] Pipeline passe sur PR avant merge
- [ ] Images Docker publiées sur GHCR
- [ ] Codecov rapport accessible

### Documentation
- [ ] `AGENTS.md` mis à jour avec les nouvelles règles v5.0
- [ ] `CHANGELOG.md` créé (`feat`, `fix`, `security`, `breaking`)
- [ ] `docs/api.md` généré depuis Swagger (`/docs`)

---

## 7. ORDRE D'EXÉCUTION RECOMMANDÉ

```
Phase P0 — Setup (2h)
  T0.1 — Migrer vers uv + pyproject.toml avec versions épinglées
  T0.2 — Initialiser Alembic + créer migration baseline
  T0.3 — Mettre à jour .env.example avec JWT_SECRET, RATE_LIMIT_*

Phase P1 — Sécurité (3h)
  T1.1 — Implémenter app/utils/auth.py (JWT)
  T1.2 — Implémenter app/utils/rate_limit.py (slowapi + Redis)
  T1.3 — Ajouter RequestIDMiddleware
  T1.4 — Protéger tous les endpoints dans main.py

Phase P2 — Cache & Performance (2h)
  T2.1 — Remplacer LLM cache in-memory → PersistentLLMCache Redis
  T2.2 — Standardiser format réponse APIResponse[T]
  T2.3 — Ajouter index DB manquants

Phase P3 — Nouveau sub-agent (2h)
  T3.1 — Créer @Debugger sub-agent
  T3.2 — Enregistrer dans sub_agent.py auto-router
  T3.3 — Ajouter endpoint /api/v1/sub-agent/debug

Phase P4 — CI/CD (2h)
  T4.1 — Remplacer docker.yml par ci.yml complet
  T4.2 — Configurer secrets GitHub (DEPLOY_HOST, DEPLOY_USER, DEPLOY_KEY)
  T4.3 — Intégrer Codecov

Phase P5 — Validation (2h)
  T5.1 — Exécuter checklist complète section 6
  T5.2 — Corriger tous les items non cochés
  T5.3 — Tag v5.0.0 + release notes

TOTAL ESTIMÉ : ~13h de développement
```

---

*AgentOS Upgrade Dossier — Généré le 2026-05-22 · HiTechTN/agentos · v4.0 → v5.0*
