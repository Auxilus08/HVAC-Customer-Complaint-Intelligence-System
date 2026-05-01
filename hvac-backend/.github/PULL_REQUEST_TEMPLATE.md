## What does this PR do?

<!-- One paragraph. What changed and why. Reference the ticket: Closes HVAC-XX -->

## Type of change

- [ ] `feat` — new feature
- [ ] `fix` — bug fix
- [ ] `refactor` — no behaviour change
- [ ] `chore` — deps, config, tooling
- [ ] `docs`
- [ ] `test`
- [ ] `perf`

## Checklist

- [ ] Tests written and passing (`make test`)
- [ ] No new linting errors (`make lint`)
- [ ] Type hints complete (`mypy app/` passes)
- [ ] `.env.example` updated if new env vars added
- [ ] No hardcoded secrets or API keys
- [ ] PII stripping verified if complaint text is touched (`make check-pii`)
- [ ] Migration created if DB schema changed (`make migration m="describe change"`)
- [ ] `alembic upgrade head` runs clean against the migration
- [ ] Docker Compose stack starts clean (`make dev`)

## How to test

<!-- Step-by-step instructions for the reviewer to verify the change. -->

## Screenshots / logs (if applicable)

<!-- Paste relevant curl output, log snippets, or screenshots. -->
