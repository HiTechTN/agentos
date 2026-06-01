# Changelog

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
