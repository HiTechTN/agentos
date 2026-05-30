# Changelog

## v5.0.0 (2026-05-30)

### Added
- **Smart LLM Router** (`app/utils/llm_router.py`) — Intelligent routing to 28+ free OpenRouter models across 8 work types with auto-detection, rate limiting, and 4-level fallback chain
- **LLM Status API** — `GET /api/v1/llm/router/status` and `GET /api/v1/llm/router/models` endpoints
- **CI/CD pipeline** (`.github/workflows/ci.yml`) — 100% coverage gate, ruff, mypy, bandit, Docker build, deploy
- **CHANGELOG.md** — Version tracking

### Added
- **Mobile App** (`mobile/`) — React Native (Expo) app with 5 screens: Dashboard, Chat, Agents, Sessions, Settings
- **Mobile CI/CD** (`.github/workflows/mobile.yml`) — EAS Build automation for Android & iOS
- **Auto port detection** (`install.sh`) — Script now finds free ports automatically to avoid conflicts
- **Docker ports env vars** (`docker-compose.yml`) — All host ports are configurable via env vars

### Changed
- Test coverage increased from 99.42% to 100% (2798/2798 statements)
- Test count increased from 592 to 663
- Coverage gate in `pyproject.toml` raised from 90% to 100%
- `pyproject.toml` omits `app/tests/*` from coverage metrics
- All API responses use `APIResponse[T]` envelope consistently
- WebSocket error handling now catches and logs send failures gracefully

### Fixed
- `get_settings()` lazy initialization now fully tested (settings.py)
- WebSocket `send_log` exception handler coverage (main.py)
- All mypy errors in test files resolved
- Ruff `UP046`, `UP042`, `F821` warnings fixed

### Security
- All secrets remain env-var based (no hardcoded credentials)
- Rate limiting enforced on all POST/PUT/DELETE endpoints
- Bandit scan passes with 0 HIGH/MEDIUM findings
