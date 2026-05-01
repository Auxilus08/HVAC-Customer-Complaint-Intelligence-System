# Branching Strategy

Source of truth for the HVAC Complaint Intelligence System team of 5.
All three repos (`hvac-backend`, `hvac-frontend`, `hvac-ml`) follow this model.

---

## Branch Hierarchy

```
main
 └── develop
      ├── feature/HVAC-42-add-umap-endpoint
      ├── fix/HVAC-51-embedding-retry-backoff
      └── chore/update-dependencies
```

| Branch | Purpose | Protected | Direct Push |
|--------|---------|-----------|-------------|
| `main` | Production-ready, tagged releases | Yes | Never |
| `develop` | Integration branch — all features land here | Yes | Never |
| `feature/*` | New capabilities | No | Author only |
| `fix/*` | Bug fixes | No | Author only |
| `chore/*` | Deps, config, tooling, non-code | No | Author only |
| `hotfix/*` | Urgent production patches | No | Author only |

---

## Branch Naming

```
feature/HVAC-{ticket}-{short-description}
fix/HVAC-{ticket}-{short-description}
chore/{description}
hotfix/{description}
```

**Examples:**
```
feature/HVAC-12-complaint-ingest-api
feature/HVAC-23-umap-scatter-endpoint
fix/HVAC-31-embedding-cache-key-collision
fix/HVAC-44-vader-threshold-boundary
chore/pin-sentence-transformers-2-7
hotfix/pii-strip-bypass-in-advisory
```

Rules:
- Ticket number is **mandatory** for `feature/` and `fix/` branches
- Description is lowercase, words separated by hyphens
- Max 50 characters after the prefix
- Branch must be created from `develop` (or `main` for `hotfix/`)

---

## Merge Rules

### feature/* and fix/* → develop
- Open a PR targeting `develop`
- Must reference the ticket: `Closes HVAC-42` in the PR body
- **1 approving review** required (any team member)
- All CI checks must pass (lint, type-check, tests)
- Branch must be **up to date** with `develop` before merge
- Merge strategy: **Squash and merge**
- Delete branch after merge

### develop → main
- Open a PR for release (e.g. `chore: release v0.3.0`)
- **2 approving reviews** required
- All CI checks must pass
- Merge strategy: **Merge commit** (preserves develop history)
- Tag the merge commit: `git tag v0.x.0`

### hotfix/* → main (and back-merge to develop)
- Branch **from `main`**, not `develop`
- PR targeting `main`, requires 1 review
- After merging to `main`, immediately open a second PR to merge into `develop`
- Merge strategy: **Merge commit** in both cases
- Tag the `main` merge: `git tag v0.x.y`

---

## Commit Message Format (Conventional Commits)

```
<type>(<scope>): <subject>

[optional body]

[optional footer: Closes HVAC-42]
```

### Types

| Type | When to use |
|------|-------------|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `chore` | Deps, config, tooling, CI — no behaviour change |
| `docs` | Documentation only |
| `refactor` | Code restructure, no behaviour change |
| `test` | Adding or fixing tests |
| `perf` | Performance improvement |
| `ci` | CI/CD pipeline changes |

### Scopes

| Scope | Covers |
|-------|--------|
| `api` | FastAPI routes, schemas, request/response |
| `worker` | Celery tasks, queues, retry logic |
| `db` | SQLAlchemy models, migrations, sessions |
| `ml` | Embeddings, clustering, sentiment, labeling |
| `frontend` | React components, hooks, API clients |
| `infra` | Docker, docker-compose, Makefile, CI |
| `security` | PII stripping, encryption, auth |

### Examples

```
feat(api): add POST /complaints/upload endpoint
fix(worker): retry embedding task on transient model error
chore(db): add index on complaints.cluster_id
test(api): add integration tests for cluster advisory endpoint
perf(ml): cache text_hash before model.encode() call
docs(infra): add docker-compose troubleshooting section
refactor(security): extract PII regex patterns to constants
ci(infra): add pre-commit checks to GitHub Actions workflow
```

---

## PR Size Guidelines

| Lines changed | Action |
|--------------|--------|
| < 200 | Ideal — reviewer can focus |
| 200–500 | Acceptable — add clear description |
| 500–1000 | Split if possible — ping reviewer before opening |
| > 1000 | Must be justified (initial scaffold, mass rename) |

---

## Release Versioning

Semantic Versioning: `MAJOR.MINOR.PATCH`

- `MAJOR` — breaking API or DB schema change
- `MINOR` — new feature, backward-compatible
- `PATCH` — bug fix, no schema change

Pre-release tags: `v0.3.0-beta.1`, `v0.3.0-rc.1`

---

## Code Freeze

Before any production release:
1. Open a `chore: freeze for v0.x.0` PR on `develop`
2. No new `feature/` PRs merge to `develop` after freeze
3. Only `fix/` and `hotfix/` PRs accepted during freeze
4. Freeze lifted after tagging `main`
