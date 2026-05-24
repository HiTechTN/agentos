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
- JAMAIS de `# pragma: no cover` sauf `if __name__ == "__main__":`

### Dependency Management
- Utiliser `uv` pour toutes les opérations de packages
- `uv add <pkg>` pour ajouter, `uv remove <pkg>` pour retirer
- JAMAIS modifier `requirements.txt` directement — généré par `uv export`
- Versions TOUJOURS épinglées dans `pyproject.toml` sous `[tool.uv.constraints]`
- TOUJOURS utiliser `--all-extras` avec `uv sync` pour inclure les dev dependencies

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
- Coverage minimum : 99% par module (cible 100%)
- Nommer les tests : `test_<unit>_<scenario>_<expected_outcome>`
- Utiliser des fixtures pytest, jamais de setup dans les test functions
- Mocker les LLM calls avec `pytest-httpx`
- Mocker Redis avec `unittest.mock.patch("redis.asyncio.from_url")` dans conftest
- Early patching obligatoire dans `conftest.py` : patcher `get_settings` au niveau module AVANT toute import
- Commande de test : `uv run pytest app/tests/ --cov=app --cov-fail-under=90 -v`

### Test Conventions (conftest.py)
- Module-level `_patcher = patch("app.config.settings.get_settings", return_value=_test_settings)` avant tout import
- Module-level `_redis_patcher = patch("redis.asyncio.from_url")` avec mock in-memory dict
- `test_settings` fixture autouse pour exposer les settings
- `auth_headers` et `admin_headers` fixtures pour les endpoints protégés
- `async_client` fixture avec `ASGITransport` pour les tests async
- `mock_llm_client` fixture patchant `app.agents.base.LLMClient`
- `mock_hitl_gateway` fixture patchant `app.agents.base.get_hitl_gateway`

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
1. `uv sync --all-extras` — ensure all deps installed
2. `ruff check app/ --fix` — lint auto-fix
3. `ruff format app/` — formatting
4. `mypy app/ --strict` — type checking (0 erreurs requis)
5. `pytest app/tests/ --cov=app --cov-fail-under=90` — tests
6. `bandit -r app/ -ll` — security scan (0 HIGH/MEDIUM)
7. `docker compose config` — validate compose file

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
- [ ] Coverage ≥ 99% (toute ligne non couverte = justification obligatoire)

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
- `app/schemas/` → modèles Pydantic et responses API uniquement

### API Conventions
- Tous les endpoints retournent `APIResponse[T]` envelope : `{"data": ..., "meta": {...}, "errors": []}`
- Status codes : 200 OK, 201 Created, 202 Accepted (async), 400 Bad Request, 401 Unauthorized, 422 Validation Error, 429 Rate Limit, 500 Internal
- Versioning : `/api/v1/` pour stable, `/api/v2/` pour beta
- Pagination : `?page=1&per_page=20` avec `meta.total`, `meta.pages`
- Auth : Bearer JWT avec `create_access_token()`, `CurrentUser` / `AdminUser` type aliases

### Performance Targets
- Endpoint `/api/v1/run` : p95 < 500ms (hors LLM)
- Endpoint `/api/v1/plan` : p95 < 200ms
- WebSocket `/ws/logs` : latence < 50ms
- DB queries : p99 < 100ms (index obligatoire sur FK et colonnes filtrées)

### Cache Architecture
- L1: dict en mémoire locale (fallback)
- L2: Redis via `Cache._get_redis()` avec fallback automatique
- `llm_cache.py` : cache LLM responses avec connect/close lifecycle
- TOUJOURS catcher les exceptions Redis et logger + fallback dict

### Redis URL Resolution
- `settings.redis_url` : peut être None (auto-detect), "memory://" (rate limit only), ou "redis://..."
- `settings.resolved_redis_url` : construit l'URL Redis complète
- Test: patcher `redis.asyncio.from_url` avec mock dict in-memory
