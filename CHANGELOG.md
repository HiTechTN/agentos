# Changelog

## [7.2.1] — 2026-06-25

### Added
- Audit report (AUDIT_REPORT.md) — Comprehensive upgrade readiness assessment

### Changed
- Version bumped to 7.2.1 (pyproject.toml, settings.py)
- pyproject.toml: version 7.1.0 → 7.2.1

### Fixed
- CI/CD workflows — All validation pipelines now green
- Mobile admin panel — Empty sections resolved, design improved
- TypeScript checks — CI failures resolved for mobile

## [7.2.0] — 2026-06-20

### Added
- **Mobile Image Attachments** — Image picker + camera support with base64 upload
- **Multimodal LLM Routing** — Automatic image-to-text routing for vision-capable models

### Fixed
- Mypy strict: 32 errors resolved across 11 files (unused `type:ignore`, untyped decorators)
- Mypy strict: 5 additional errors resolved for mypy 1.14.1 compatibility

### Changed
- Version bumped to 7.2.0

### Refactored
- guide.html — Glassmorphism CSS, Inter fonts, animations, multi-language support
- Documentation — All version references updated to v7.1.0 across docs/, templates/, mobile configs
- Mobile build instructions — Headless APK build documented in AGENTS.md

## [7.1.0] — 2026-06-03

### Added
- **Model Auto-Discovery** (`app/utils/model_discovery.py`) — `ModelDiscoveryEngine` fetches free OpenRouter models, auto-classifies by WorkType (code_gen, code_agent, reasoning, content, fast, multimodal, debug, general) using regex scoring, benchmarks latency, upserts `discovered_models` table
- **Rotation Engine** (`app/utils/rotation_engine.py`) — `RotationEngine` selects top model by rotated weight (weighted random from top 3), tracks success/error/rate-limit events, dynamic weight updates (+0.05 success, -0.20 error, -0.15 rate-limit), 429 auto-ban
- **SmartRouter DB Integration** (`app/utils/llm_router.py`) — `_reload_dynamic_models()` queries DB for active models, `_get_candidates()` merges dynamic (priority) + hardcoded FREE_MODELS (fallback), wired in sync route and scheduler
- **Migration 004** (`app/migrations/versions/004_model_registry.py`) — 3 tables: `discovered_models`, `model_rotation_log`, `discovery_snapshots` (applied)
- **Model API** (`app/routes/models.py`) — 5 endpoints under `/api/v1/llm/models/`: catalog, sync, health, disable, rotation status
- **CLI** (`scripts/discover_models.py`) — `sync`, `--bench`, `--report`, `--health`, `--reset`, `--disable` commands
- **Scheduler Jobs** — Daily model discovery (`0 3 * * *`), health check every 30 minutes

### Changed
- Version bumped to 7.1.0
- Test count: 955 → 1054 (99% coverage)
- `SmartLLMRouter.select_model()` / `complete()` now check DB-discovered models before hardcoded FREE_MODELS
- Sync endpoint and scheduler call `smart_router._reload_dynamic_models()` after discovery

### Infrastructure
- OpenRouter API key configured in production `.env`
- `scripts/discover_models.py` — standalone CLI for manual sync + diagnostics
- 21 free models live-synced from OpenRouter to PostgreSQL

### Fixed
- `::jsonb` → `CAST(... AS jsonb)` for asyncpg compatibility
- `str()` → `json.dumps()` for JSONB serialization (single-quote vs double-quote)

## [7.0.0] — 2026-06-02

### Added
- Tree of Thoughts (ToT) reasoning engine with MCTS scoring for complex tasks
- GraphRAG knowledge graph (NetworkX + PostgreSQL) for entity-relation extraction
- VRAM Manager with 12GB GPU budget tracking and automatic model selection
- AutoCorrector — automatic stderr→fix retry loop for sandbox code execution  
- WasmRunner — lightweight code execution with compile cache and 5ms timeout
- EphemeralFS — per-workspace temp directories with auto-cleanup
- AgentBus — Redis Pub/Sub messaging for agent-to-agent communication
- ComputerUseTools — screen interaction tools (disabled by default, feature flag)
- Production config validator — blocks startup on unsafe settings
- Alembic migration 003 for GraphRAG tables (graph_entities, graph_edges)
- ContextEnricher integration into BaseAgent system prompt injection
- EpisodicMemory recording in orchestrator workflow finalization
- TreeOfThoughts integration in planner for complex goals
- New settings: VRAM, ToT, AutoCorrector, WasmRunner, EphemeralFS, AgentBus, ComputerUse config

### Changed
- Version bumped to 7.0.0
- .env.example updated to v7.0 with all new settings documented
- BaseAgent.execute() enriches system prompt with ContextEnricher (memories, skills, knowledge)
- Orchestrator._finalize() records task outcome in EpisodicMemory
- DevAgent includes AutoCorrector for future sandbox code correction
- Planner.create_plan() runs TreeOfThoughts for complex goals
- CI pipeline updated to run on push to main/develop, includes new modules in coverage

### Fixed
- All new modules pass ruff strict, mypy strict, and bandit HIGH/MEDIUM
- ConfigValidator catches default JWT secrets before production deployment

## v6.0.0 (2026-06-01)

### Added
- **Intelligence Engine** — Self-improving system with 5 modules and 8 API endpoints
- **Episodic Memory** (`app/memory/episodic.py`) — `TaskOutcome` dataclass, `EpisodicMemory.record()`, `.recall_similar()`, `.get_best_strategy()`, `.get_stats()` — tracks every task execution with quality scoring, workspace isolation, and strategy tracking
- **Skills Registry** (`app/skills/registry.py`) — `SkillsRegistry.extract_from_outcome()` (LLM auto-discovery from successful tasks), `.find_relevant()` (keyword scoring), `.record_usage()` (reinforcement: +0.05 success, -0.1 failure, auto-disable at 4 failures), `.get_all()`
- **Knowledge Base** (`app/memory/knowledge.py`) — `KnowledgeBase.add()`, `.query()` (ILIKE keyword search with usage_count increment), `.build_context_block()` (markdown formatted for prompt injection), `.validate()` — supports 6 kinds: api_pattern, code_pattern, constraint, best_practice, domain_fact, failure_mode
- **Self-Reflection Engine** (`app/learning/reflection.py`) — `SelfReflectionEngine.should_reflect()` (threshold=10 tasks), `.run(force)` (collect → LLM reflect → extract skills → record evolutions → save report), `.summarize_memories()`, `.record_evolution()`
- **Context Enricher** (`app/learning/context_enricher.py`) — `ContextEnricher.enrich()` auto-injects past experiences, relevant skills, and domain knowledge into agent system prompts (capped at 2000 chars)
- **Intelligence API** (`app/api/intelligence.py`) — 8 endpoints under `/api/v1/intelligence`: memories list/stats, skills list, knowledge CRUD, reflection trigger, reports list, evolutions list — all JWT-protected
- **Nightly Reflection** (`app/scheduler.py`) — Cron `0 2 * * *`, iterates all active workspaces, triggers `SelfReflectionEngine.run(force=True)` daily
- **Alembic Migration** (`002_intelligence_engine.py`) — 5 new tables: `episodic_memories`, `skills`, `knowledge_entries`, `agent_evolutions`, `reflection_reports` with UUID PKs, JSONB, pgvector extension
- **Intelligence Engine Tests** (264 tests) — 100% coverage for all 5 modules + API endpoints

### Changed
- Version bumped to 6.0.0
- Test count: 716 → 980
- Module responsibilities updated: `app/learning/` and `app/skills/` added
- AGENTS.md updated with full Intelligence Engine rules
- `app/main.py` — intelligence_router wired at `/api/v1/intelligence`

### Infrastructure
- `app/scheduler.py` — Added nightly reflection task registration on start
- `settings.nightly_reflection_cron` — Configurable cron expression (default `0 2 * * *`)

## v5.1.0 (2026-05-31)

### Added
- **User Auth System** (`app/routes/auth.py`) — Email/password registration, JWT login, OAuth (Google/GitHub), user profile endpoint
- **Auth Schemas** (`app/schemas/auth.py`) — Pydantic models with email/password validators, auto-lowercase, min 8 char password
- **Admin Panel** (`app/routes/admin.py`) — 7 endpoints: settings read/write, service health (DB/Redis/Ollama/OpenRouter), LLM provider browser, model selection, user management
- **Mobile Admin Screen** (`mobile/app/(tabs)/admin.tsx`) — System status, env editor, LLM provider selector, user list
- **Mobile Registration** (`mobile/app/register.tsx`) — Create account with email/password
- **Mobile OAuth** (`mobile/app/oauth.tsx`) — Deep-link OAuth callback handler for Google/GitHub
- **Multi-Modal Chat** (`mobile/app/(tabs)/chat.tsx`) — Image picker + camera attachments, base64 upload
- **Admin auto-promotion** — Users matching `ADMIN_EMAILS` env var get admin role automatically
- **Build system** (`build/build.sh`) — One-command multi-platform build: wheel → tar.gz → .deb → .rpm → checksums
- **Linux packages** — Pre-built .deb (Debian/Ubuntu) and .rpm (Fedora/RHEL) with `/usr/local/bin/agentos` CLI
- **agentos CLI** — `agentos init|up|down|logs|status|test|shell|update|version` commands
- **Auth route tests** — 17 tests covering register, login, OAuth, /me endpoints
- **Admin route tests** — 16 tests covering settings, services, LLM providers, model selection, users
- **Schema validator tests** — 3 tests for email format, password length, email lowercasing

### Changed
- Test coverage: 100% (3241/3241 statements)
- Test count: 663 → 716
- Version bumped to 5.1.0 everywhere (pyproject.toml, tauri configs, Cargo.toml, landing page)
- `install.sh` — Interactive menu (Docker/pkg/PIP/Desktop/Mobile), downloads from GitHub releases
- Landing page (`docs/index.html`) — Updated stats, features (auth, admin, mobile, multi-modal)
- `importlib.reload` replaced with direct `setattr` on settings singleton in admin routes

### Fixed
- `from __future__ import annotations` removed from auth.py and admin.py (broke FastAPI type detection)
- `_mock_db_session()` pattern — Mock() not AsyncMock for execute.return_value (Python 3.13 compat)
- Settings patcher conftest compatibility — Admin routes mutate singleton instead of reload
- Mock `name=` kwarg usage (sets display name, not `.name` attribute)
- Admin test state leak — Settings restored after each modification test
- `smart_router.get_usage_report()` missing `await` in admin route
- Import paths in admin tests (`app.routes.admin` → `app.memory.session`)
- Build script: tar.gz self-destruct bug, RPM %install path issue, pyproject.toml version alignment

## v5.0.0 (2026-05-30)

### Added
- **Smart LLM Router** (`app/utils/llm_router.py`) — Intelligent routing to 28+ free OpenRouter models across 8 work types with auto-detection, rate limiting, and 4-level fallback chain
- **LLM Status API** — `GET /api/v1/llm/router/status` and `GET /api/v1/llm/router/models` endpoints
- **CI/CD pipeline** (`.github/workflows/ci.yml`) — 100% coverage gate, ruff, mypy, bandit, Docker build, deploy
- **Mobile App** (`mobile/`) — React Native (Expo) app with 5 screens: Dashboard, Chat, Agents, Sessions, Settings
- **Mobile CI/CD** (`.github/workflows/mobile.yml`) — EAS Build automation for Android & iOS
- **Auto port detection** (`install.sh`) — Script now finds free ports automatically to avoid conflicts
- **Docker ports env vars** (`docker-compose.yml`) — All host ports are configurable via env vars

### Changed
- Test coverage increased from 99.42% to 100% (2798/2798 statements)
- Test count increased from 592 to 663
- Coverage gate in `pyproject.toml` raised from 90% to 100%

### Fixed
- `get_settings()` lazy initialization now fully tested (settings.py)
- WebSocket error handling, mypy errors, ruff warnings

### Security
- All secrets remain env-var based (no hardcoded credentials)
- Rate limiting enforced on all POST/PUT/DELETE endpoints
