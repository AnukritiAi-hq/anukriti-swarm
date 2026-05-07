# GitHub Labels

> Recommended label set for Anukriti Swarm. Apply via GitHub UI or `gh label create`.

---

## Type Labels

| Label | Color | Description |
|-------|-------|-------------|
| `bug` | `#d73a4a` | Something isn't working |
| `enhancement` | `#a2eeef` | New feature or capability |
| `research` | `#7057ff` | Research investigation or experiment |
| `documentation` | `#0075ca` | Documentation improvements |
| `refactor` | `#e4e669` | Code restructuring (no functional change) |
| `infrastructure` | `#f9d0c4` | CI/CD, tooling, repo config |

## Priority Labels

| Label | Color | Description |
|-------|-------|-------------|
| `priority: critical` | `#b60205` | Blocks all work |
| `priority: high` | `#d93f0b` | Important, address this sprint |
| `priority: medium` | `#fbca04` | Normal priority |
| `priority: low` | `#0e8a16` | Nice to have |

## Agent Labels

| Label | Color | Description |
|-------|-------|-------------|
| `agent: orchestrator` | `#1d76db` | Orchestrator agent |
| `agent: population` | `#5319e7` | Population agents |
| `agent: chromosome` | `#006b75` | Chromosome agents |
| `agent: pharmacogene` | `#b4a8d1` | Pharmacogene agents |
| `agent: retrieval` | `#c5def5` | Retrieval agent |
| `agent: verification` | `#d4c5f9` | Verification agent |
| `agent: narrative` | `#bfdadc` | Narrative agent |

## Status Labels

| Label | Color | Description |
|-------|-------|-------------|
| `triage` | `#ededed` | Needs triage |
| `in-progress` | `#0052cc` | Actively being worked on |
| `blocked` | `#b60205` | Blocked by dependency |
| `needs-review` | `#fbca04` | Ready for review |

## Domain Labels

| Label | Color | Description |
|-------|-------|-------------|
| `domain: memory` | `#c2e0c6` | Memory layer |
| `domain: mcp` | `#fef2c0` | MCP integration |
| `domain: safety` | `#f9d0c4` | Safety and verification |
| `domain: workflow` | `#d4c5f9` | Pipeline and DAG execution |

---

## Setup Script

```bash
# Create all labels (requires gh CLI)
gh label create "bug" --color "d73a4a" --description "Something isn't working"
gh label create "enhancement" --color "a2eeef" --description "New feature or capability"
gh label create "research" --color "7057ff" --description "Research investigation"
gh label create "agent: orchestrator" --color "1d76db" --description "Orchestrator agent"
# ... (extend for all labels above)
```
