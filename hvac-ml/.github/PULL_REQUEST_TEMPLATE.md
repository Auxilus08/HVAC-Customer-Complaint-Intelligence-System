## What does this PR do?

<!-- One paragraph. What changed and why. Reference the ticket: Closes HVAC-XX -->

## Type of change

- [ ] `feat` — new pipeline feature or model change
- [ ] `fix` — bug fix
- [ ] `refactor` — no behaviour change
- [ ] `chore` — deps, config, tooling
- [ ] `docs`
- [ ] `test`

## Checklist

- [ ] Tests written and passing (`pytest tests/ -v`)
- [ ] No new linting errors (`ruff check .`)
- [ ] Type hints complete (`mypy pipeline/` passes)
- [ ] PII stripping verified if complaint text is touched
- [ ] `.env.example` updated if new env vars added
- [ ] No hardcoded secrets or API keys
- [ ] `random_state=42` preserved on all UMAP fits if clustering changed
- [ ] Two-UMAP invariant maintained (50D cluster, 2D viz — never mixed)
- [ ] Pipeline notebook updated if end-to-end flow changed

## How to test

<!-- Step-by-step instructions for the reviewer to verify the change. -->

## Model / metric changes (if applicable)

<!-- Silhouette score before/after, any threshold changes, benchmark comparisons. -->
