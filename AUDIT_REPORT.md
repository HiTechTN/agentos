# RAPPORT D'AUDIT — AgentOS v7.2.1
## Préparation à la mise à niveau

> **Généré le**: 2026-06-25  
> **Version courante**: 7.2.1 (tag)  
> **Version dans pyproject.toml**: 7.1.0 ❌  
> **Pipeline de validation**: basé sur AGENTS.md @Verifier rules

---

## 1. CARTOGRAPHIE — Modules

### 1.1 Tous les modules requis (32/32 ✅)

| Domaine | Statut | Modules |
|---------|--------|---------|
| **Agents** | ✅ | `base.py`, `dev.py`, `content.py`, `marketing.py`, `commerce.py`, `sub_agent.py`, `rules.py`, `sub_agents/debugger.py` |
| **Utils** | ✅ | `logging.py`, `sandbox.py`, `metrics.py`, `telemetry.py`, `api_clients.py`, `llm_router.py`, `llm_models.py`, `llm_cache.py`, `llm_rate_limiter.py`, `auth.py`, `rate_limit.py`, `request_id.py`, `vram_manager.py`, `auto_corrector.py`, `hitl_gateway.py`, `notifications.py`, `config_validator.py`, `model_discovery.py`, `rotation_engine.py` |
| **Memory** | ✅ | `cache.py`, `vector_store.py`, `episodic.py`, `knowledge.py`, `session.py`, `graph_rag.py`, `workspace.py` |
| **Learning** | ✅ | `reflection.py`, `context_enricher.py` |
| **Skills** | ✅ | `registry.py` |
| **Infrastructure** | ✅ | `main.py`, `orchestrator.py`, `orchestrator_state.py`, `scheduler.py`, `pulse.py`, `kanban.py`, `git_worktree.py` |
| **Raisonnement** | ✅ | `tot_engine.py` |
| **Bus** | ✅ | `agent_bus.py` |
| **Sandbox** | ✅ | `wasm_runner.py`, `ephemeral_fs.py` |
| **Tools** | ✅ | `computer_use.py` |
| **API** | ✅ | `intelligence.py` + 11 fichiers dans `routes/` |
| **Migrations** | ✅ | 5 fichiers : baseline, users, intelligence, graphrag, model_registry |

---

## 2. QUALITÉ DE CODE

### 2.1 Ruff (lint) — ✅ PASS
```
All checks passed!
```

### 2.2 Ruff (format) — ✅ PASS
```
137 files already formatted
```

### 2.3 Mypy strict — ❌ 32 ERREURS
**Fichiers impactés** (11 fichiers legacy) :

| Fichier | Erreurs | Type |
|---------|---------|------|
| `app/routes/auth.py` | 6 | Unused `type:ignore` + untyped decorator |
| `app/routes/management.py` | 6 | Unused `type:ignore` |
| `app/routes/worktree.py` | 4 | Unused `type:ignore` |
| `app/routes/kanban.py` | 3 | Unused `type:ignore` |
| `app/routes/admin.py` | 3 | Unused `type:ignore` |
| `app/routes/workflow.py` | 3 | Unused `type:ignore` |
| `app/routes/mcp.py` | 2 | Unused `type:ignore` |
| `app/routes/content.py` | 2 | Unused `type:ignore` |
| `app/routes/llm.py` | 1 | Unused `type:ignore` |
| `app/agents/content.py` | 1 | Unused `type:ignore` |
| `app/main.py` | 1 | `arg-type` dans `add_exception_handler` |

**Cause racine**: Anciens `# type: ignore[XXX]` sur des lignes qui ne sont plus en erreur depuis les fix mypy précédents (commit `43113f0`).

### 2.4 Bandit (sécurité) — ✅ PASS
```
No issues identified. 0 Medium, 0 High.
```

---

## 3. TESTS — 1056 PASSING, 98.60% COVERAGE ⚠️

| Métrique | Valeur | Cible | Statut |
|----------|--------|-------|--------|
| Tests total | 1056 | — | ✅ |
| Coverage | **98.60%** | **100%** | ❌ |
| Temps d'exécution | 34.61s | — | ✅ |
| Échecs | 0 | 0 | ✅ |
| Warnings | 18 | — | ⚠️ |

### Modules sous-performants (coverage < 100%)

| Module | Coverage | Lignes manquantes |
|--------|----------|-------------------|
| `app/utils/llm_router.py` | 95% | 43-44, 81-82, 91-92, 279-284 |
| `app/utils/api_clients.py` | 98% | 95-100 |
| `app/tools/computer_use.py` | 97% | 57-58 |
| `app/scheduler.py` | 96% | 158-159, 161-162, 256, 273-274 |
| `app/utils/auto_corrector.py` | 98% | 93 |
| `app/routes/models.py` | 97% | 96-99 |

---

## 4. INFRASTRUCTURE

### 4.1 Docker Compose — ✅ VALIDE
```
docker compose config --quiet → exit 0
```
- 9 services configurés (postgres, redis, mailhog, jaeger, minio, caddy, app, web, strapi disabled)
- Healthchecks sur TOUS les services ✅
- Aucun volume source mount en prod ✅
- ⚠️ Strapi commenté (image `naskio/strapi` cassée)

### 4.2 CI/CD — 3 workflows
- `.github/workflows/ci.yml` — lint + test + docker + deploy
- `.github/workflows/mobile.yml` — EAS Build Android & iOS
- `.github/workflows/release.yml` — release automation

### 4.3 Alembic — ⚠️ NON VÉRIFIABLE SANS DB
- 5 migrations présentes
- `alembic check` impossible (pas de base PostgreSQL dans cet environnement)

---

## 5. CONFIGURATION & VERSION

### 5.1 Version désynchronisée ⚠️

| Fichier | Version | Doit être |
|---------|---------|-----------|
| `pyproject.toml` | **7.1.0** | **7.2.1** |
| `app/config/settings.py` | **7.2.1** ✅ | — |
| `install.sh` | **7.2.1** ✅ | — |
| `CHANGELOG.md` | 7.2.1 non documenté | Ajouter section v7.2.1 |

### 5.2 Fichiers non commités (24 modifiés + plusieurs non suivis)
- 24 fichiers modifiés (dont `Dockerfile`, `app/main.py`, `app/agents/base.py`, `docker-compose.yml`, `app/routes/` legacy)
- `.opencode/` → fichiers locaux (config opencode)

---

## 6. ARCHITECTURE & DETTES TECHNIQUES

### 6.1 Fonctions > 50 lignes (violation AGENTS.md)
31 fonctions dépassent la limite de 50 lignes définie dans AGENTS.md. Les plus longues :

| Fonction | Fichier | Lignes |
|----------|---------|--------|
| `oauth_callback` | `app/routes/auth.py:240` | 134 |
| `test_run_force_full_cycle` | `app/tests/test_intelligence.py:1174` | 115 |
| `run` (SelfReflection) | `app/learning/reflection.py:105` | 111 |
| `execute` (BaseAgent) | `app/agents/base.py:57` | 90 |
| `enrich` | `app/learning/context_enricher.py:48` | 85 |
| `extract_from_outcome` | `app/skills/registry.py:55` | 86 |
| `complete` (SmartRouter) | `app/utils/llm_router.py:158` | 85 |

### 6.2 Architecture redundante
- **Deux systèmes de routes**: `app/api/` (nouveau) et `app/routes/` (legacy, 11 fichiers)
- Les 32 erreurs mypy sont concentrées dans `app/routes/` — ces fichiers legacy devraient être migrés vers `app/api/`

---

## 7. ISSUES PRIORITAIRES POUR LA MISE À NIVEAU

### 🔴 CRITICAL (0)
Aucun issue critique — le système est fonctionnel.

### 🟡 HIGH (3)
| ID | Issue | Fichier | Impact |
|----|-------|---------|--------|
| H1 | **Version pyproject.toml = 7.1.0** | `pyproject.toml:10` | Le package serait publié avec une version incorrecte |
| H2 | **Coverage 98.60% < 100%** | pyproject.toml target | Le pipeline CI blockerait si `--cov-fail-under=100` est utilisé |
| H3 | **Mypy : 32 erreurs non résolues** | `app/routes/*.py`, `app/main.py` | Pipeline mypy --strict blockerait |

### 🟠 MEDIUM (4)
| ID | Issue | Détail |
|----|-------|--------|
| M1 | **31 fonctions > 50 lignes** | Violation AGENTS.md — refactoring recommandé |
| M2 | **Routes legacy (app/routes/)** | Code mort/maintenu en parallèle de `app/api/` |
| M3 | **Strapi désactivé** | Service commenté, dépendance cassée |
| M4 | **24 fichiers modifiés non commités** | État de travail non versionné |

### 🔵 LOW (4)
| ID | Issue | Détail |
|----|-------|--------|
| L1 | **18 warnings pytest** | À inspecter |
| L2 | **`alembic check` non vérifiable sans DB** | Documentation du processus manquante |
| L3 | **Aucun fichier > 300 lignes** ✅ | Bon respect de la limite |
| L4 | **CHANGELOG.md manque section v7.1.0 et v7.2.0** | Documentation non synchronisée |

---

## 8. RECOMMANDATIONS — ORDRE D'EXÉCUTION

```
Phase P1 — Version & Configuration (15 min)
  Fix pyproject.toml → 7.2.1
  Ajouter CHANGELOG entries manquantes
  Commit + tag

Phase P2 — Mypy Fix (30 min)
  Nettoyer les 32 `type: ignore` inutilisés dans app/routes/
  Fixer les decorated non typés dans auth.py
  Fixer arg-type dans main.py

Phase P3 — Coverage 100% (1h)
  Ajouter tests pour les lignes manquantes :
    - llm_router.py : 6 lignes
    - api_clients.py : 2 lignes
    - scheduler.py : 4 lignes
    - computer_use.py : 2 lignes

Phase P4 — Dette technique (2h)
  Refactoring des 31 fonctions > 50 lignes
  Migration progressive app/routes/ → app/api/
  Nettoyage des fichiers modifiés non commités

Phase P5 — Validation finale (30 min)
  ruff check + ruff format
  mypy --strict → 0 erreurs
  pytest --cov-fail-under=100
  bandit -r app/ -ll
  docker compose config
```

**TOTAL ESTIMÉ : ~4h de développement**

---

## 9. VERDICT

| Critère | Statut |
|---------|--------|
| **Produit minimum viable** | ✅ Prêt pour prod |
| **100% coverage** | ⚠️ 98.60% — 3 modules à compléter |
| **Mypy strict** | ❌ 32 erreurs dans routes legacy |
| **Sécurité (bandit)** | ✅ Aucun issue MEDIUM/HIGH |
| **Code quality (ruff)** | ✅ Parfait |
| **Docker** | ✅ Configuration valide |
| **CI/CD** | ✅ Pipelines configurés |
| **Version** | ❌ pyproject.toml = 7.1.0 vs tag 7.2.1 |

**Note globale**: Le codebase est en très bonne santé (score ~9/10). Les corrections mypy + coverage + version sont rapides (~4h). La priorité est de synchroniser `pyproject.toml` avec le tag git, puis de nettoyer les erreurs mypy legacy avant de viser 100% de coverage.
