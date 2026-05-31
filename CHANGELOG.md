# Changelog

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
