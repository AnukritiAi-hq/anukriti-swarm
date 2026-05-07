# Branch Strategy

> Git branching model for Anukriti Swarm development.

---

## Branch Types

```
main ─────────────────────────────────────────────────▶ (stable, protected)
  │
  ├── feat/orchestrator-dag-execution ──── PR ──▶ main
  ├── feat/population-sas-agent ────────── PR ──▶ main
  ├── fix/memory-layer-timeout ─────────── PR ──▶ main
  ├── docs/architecture-update ─────────── PR ──▶ main
  └── experiment/llm-grounding-eval ────── PR ──▶ main
```

## Branch Naming

| Prefix | Purpose | Example |
|--------|---------|---------|
| `feat/` | New features or agents | `feat/chromosome-agent-haplotyping` |
| `fix/` | Bug fixes | `fix/vcf-parser-quality-filter` |
| `docs/` | Documentation only | `docs/mcp-integration-guide` |
| `refactor/` | Code restructuring | `refactor/base-agent-interface` |
| `experiment/` | Research experiments | `experiment/qdrant-embedding-eval` |
| `chore/` | Tooling, CI, config | `chore/add-github-actions` |

## Rules

1. **`main` is always stable** — All merges via PR, all checks must pass
2. **Short-lived branches** — Merge within days, not weeks
3. **One concern per branch** — Don't mix features with refactors
4. **Delete after merge** — Keep branch list clean
5. **Rebase preferred** — Keep linear history when possible

## Protection Rules (for `main`)

- Require PR review (1 reviewer minimum)
- Require status checks to pass (lint, test)
- No direct pushes
- No force pushes

## Workflow

```
1. Create branch from main:    git checkout -b feat/my-feature main
2. Make changes with micro-commits
3. Push and open PR:           git push -u origin feat/my-feature
4. Address review feedback
5. Squash or rebase merge into main
6. Delete branch
```

## Research Branches

For `experiment/` branches:
- May have longer lifetimes (up to 2 weeks)
- Results documented before merge
- Negative results are valid outcomes — still merge the documentation
- Code quality standards still apply
