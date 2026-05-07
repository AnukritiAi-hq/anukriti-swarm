# Commit Message Conventions

> Based on [Conventional Commits](https://www.conventionalcommits.org/) v1.0.0.

---

## Format

```
<type>(<scope>): <description>

<body>

<footer>
```

## Types

| Type | Purpose |
|------|---------|
| `feat` | New feature or agent capability |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `test` | Adding or updating tests |
| `chore` | Tooling, CI, config, dependencies |
| `perf` | Performance improvement |
| `style` | Formatting (no logic change) |

## Scopes

| Scope | Area |
|-------|------|
| `agents` | Agent framework |
| `arch` | Architecture docs |
| `orchestrator` | Orchestrator agent |
| `population` | Population agents |
| `chromosome` | Chromosome agents |
| `retrieval` | Retrieval agent |
| `verification` | Verification agent |
| `narrative` | Narrative agent |
| `memory` | Memory layer |
| `mcp` | MCP integration |
| `workflow` | Pipeline/DAG |
| `api` | Backend API |

## Examples

```
feat(agents): add base agent abstraction with LangGraph compatibility
fix(memory): resolve vector store connection timeout on large queries
docs(arch): update data flow diagram with verification gate
refactor(orchestrator): extract DAG compilation into separate module
test(chromosome): add unit tests for VCF variant filtering
chore: update ruff to v0.5.0 and fix new lint warnings
```

## Rules

1. **Subject line ≤ 72 characters**
2. **Imperative mood** — "add feature" not "added feature"
3. **No period** at end of subject line
4. **Body** explains *what* and *why* (not *how*)
5. **Footer** for breaking changes and issue references

## Breaking Changes

```
feat(agents)!: redesign BaseAgent interface

BREAKING CHANGE: execute() now returns SwarmState instead of AgentResult.
All agent subclasses must be updated.
```

## Micro-Commit Philosophy

- Each commit is a single logical change
- Commits should be independently reviewable
- Prefer many small commits over one large commit
- Each commit should leave the codebase in a working state
