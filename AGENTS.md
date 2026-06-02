# AGENTS.md — AgentOS Project Rules v6.0
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
- `app/learning/` → self-reflection et context enrichment uniquement
- `app/skills/` → registre de compétences auto-découvertes uniquement
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

### Smart LLM Router (app/utils/llm_router.py)
- Toujours utiliser `llm_complete()` de `app.utils.api_clients` pour les appels LLM
- Disponible via `api_clients.py` qui expose `smart_router.complete()` sous `llm_complete()`
- `WorkType` enum avec 8 catégories : CODE_GEN, CODE_AGENT, REASONING, CONTENT, FAST, MULTIMODAL, DEBUG, GENERAL
- Détection automatique via `detect_work_type(prompt, agent_name)` avec scoring de mots-clés
- Fallback à 4 niveaux : modèle préféré → modèle suivant dans la liste → Ollama local → réponse dégradée
- Rate limiting auto par modèle (1 req/min fenêtre glissante, 100 req/jour, bannissement après 3 erreurs consécutives)
- 28+ modèles OpenRouter gratuits catalogués dans `FREE_MODELS` triés par priorité par catégorie
- Endpoints API : `GET /api/v1/llm/router/status` et `GET /api/v1/llm/router/models`
- Lifetime : `smart_router.close()` appelé dans le shutdown du lifespan de main.py

---

## INTELLIGENCE ENGINE (v6.0)

### Intelligence Endpoints
- Base path: `/api/v1/intelligence`
- Auth: Tous les endpoints requièrent auth JWT (`CurrentUser` / `AdminUser`)
- Modules: `app/api/intelligence.py` — 8 endpoints (memories, skills, knowledge CRUD, reflection, reports, evolutions)

### Episodic Memory (`app/memory/episodic.py`)
- `TaskOutcome` dataclass : workspace_id, task_type, prompt_summary, outcome, quality_score, strategy_used
- `EpisodicMemory.record(outcome)` — INSERT dans `episodic_memories` avec UUID
- `EpisodicMemory.recall_similar(task_type, workspace_id, limit, outcome_filter)` — SELECT trié par quality_score DESC
- `EpisodicMemory.get_best_strategy(task_type, workspace_id)` — renvoie la meilleure stratégie
- `EpisodicMemory.get_stats(workspace_id, days)` — agrégations par task_type (total, success, avg quality, avg duration)
- Table: `episodic_memories` (UUID PK, JSONB context_tags, workspace_id + created_at indexes)

### Skills Registry (`app/skills/registry.py`)
- `SkillsRegistry.extract_from_outcome(workspace_id, task_description, successful_approach, task_type, memory_id)` — LLM auto-extraction avec validation de slug
- `SkillsRegistry.find_relevant(task_description, workspace_id, limit, min_confidence)` — keyword scoring + confidence
- `SkillsRegistry.record_usage(workspace_id, slug, succeeded)` — reinforcement learning (+0.05 success, -0.1 failure, désactivation à 4 échecs)
- `SkillsRegistry.get_all(workspace_id, category)` — liste toutes les compétences actives
- Table: `skills` (UUID PK, unique(workspace_id, slug), JSONB trigger_patterns + source_memory_ids)

### Knowledge Base (`app/memory/knowledge.py`)
- `KnowledgeBase.add(workspace_id, kind, title, content, source_type, confidence, tags)` — INSERT avec validation
- `KnowledgeBase.query(workspace_id, keywords, kind, limit, min_confidence)` — ILIKE ANY search, incrémente usage_count
- `KnowledgeBase.build_context_block(workspace_id, keywords, max_chars)` — formate en markdown pour injection dans system prompts
- `KnowledgeBase.validate(workspace_id, entry_id, is_valid)` — ajuste la confiance (+0.1 valid, -0.2 invalid)
- 6 kinds: api_pattern, code_pattern, constraint, best_practice, domain_fact, failure_mode
- Table: `knowledge_entries` (UUID PK, JSONB tags, confidence + usage_count indexes)

### Self-Reflection Engine (`app/learning/reflection.py`)
- `SelfReflectionEngine.should_reflect()` — COUNT tâches depuis dernier rapport, threshold = 10
- `SelfReflectionEngine.run(force)` — collecte memories → LLM reflection → extract skills → record evolution → save report
- `SelfReflectionEngine._llm_reflect(summary)` — appel LLM avec `_REFLECTION_SYSTEM` prompt, parse JSON structuré
- Détection auto des patterns, recommandations, nouvelles connaissances, agent evolutions
- Table: `reflection_reports` (UUID PK, JSONB top_patterns + recommendations + model_performance)
- Table: `agent_evolutions` (UUID PK, JSONB after_state)

### Context Enricher (`app/learning/context_enricher.py`)
- `ContextEnricher.enrich(base_system, task_description, task_type, workspace_id, flags)` — augmente le system prompt
- 3 blocs optionnels : memories (recall_similar), skills (find_relevant), knowledge (build_context_block)
- Cap à 2000 chars pour le bloc d'enrichissement
- Usage typique : `BaseAgent.build_system_prompt()` appelle enricher avant chaque exécution

### Scheduler Nightly Reflection
- Cron: `0 2 * * *` (2am daily, configurable via `settings.nightly_reflection_cron`)
- Itère sur tous les workspace_id distincts dans `episodic_memories`
- Appelle `SelfReflectionEngine.run(force=True)` pour chaque workspace

### Migration Alembic
- Révision: `002_intelligence_engine.py` (revise `7e3f1a2b5c0d`)
- Crée 5 tables: `episodic_memories`, `skills`, `knowledge_entries`, `agent_evolutions`, `reflection_reports`
- Active pgvector extension
- UUID PKs, JSONB pour données flexibles, unique constraint sur skills(workspace_id, slug)

---

## NOUVEAUX MODULES v7.0
- VRAMManager : toujours passer work_type pour le bon modèle Ollama
- TreeOfThoughts : activer seulement si task.complexity > 0.7
- GraphRAG : extract_and_store() après chaque session
- AutoCorrector : wrap TOUS les appels sandbox DevAgent
- WasmRunner : pour outils légers (<5ms) uniquement
- AgentBus : pour spawn de sous-agents spécialisés
- ComputerUseTools : désactivé par défaut, activer via COMPUTER_USE_ENABLED=true

## VRAM BUDGET RULES (12GB GPU)
- TOT_MAX_BRANCHES = 2 (jamais 3 sans vérification GPU libre)
- Un seul modèle Ollama en VRAM à la fois (VRAMManager s'en charge)
- Pour tâches FAST : utiliser qwen2.5:7b-instruct-q4_K_M (4.5GB) — libère 7GB
- Ne jamais lancer Computer Use et Tree of Thoughts simultanément
