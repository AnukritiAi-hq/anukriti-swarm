# Documentation Standards

> Guidelines for maintaining research-grade documentation across Anukriti Swarm.

---

## Principles

1. **Document decisions, not just code** — Explain *why*, not just *what*
2. **Keep docs near code** — Module docstrings > separate wiki pages
3. **Version with code** — Documentation lives in the repo, not external tools
4. **Research-grade** — Cite sources, state assumptions, note limitations

## File Types

| Location | Purpose | Format |
|----------|---------|--------|
| Module docstrings | API documentation | Google-style Python docstrings |
| `docs/` | Project-level guides | Markdown |
| `architecture/` | System design | Markdown with ASCII diagrams |
| `docs/adr/` | Architecture decisions | ADR template |
| `experiments/` | Research logs | Markdown + notebooks |

## Markdown Standards

- Use ATX headers (`#`, `##`, `###`)
- One sentence per line (for clean diffs)
- Use tables for structured comparisons
- Use fenced code blocks with language tags
- Include a top-level description after the title

```markdown
# Title

> One-line description of this document's purpose.

---

## Section
```

## Diagrams

- Use ASCII art for architecture diagrams (renders everywhere)
- Place in `architecture/` directory
- Keep diagrams under 80 characters wide when possible
- Update diagrams when architecture changes

## Module Documentation

Every Python module must have:

```python
"""Module title — one-line summary.

Extended description explaining the module's role in the system,
its responsibilities, and how it fits into the agent architecture.

Future responsibilities:
- Planned feature 1
- Planned feature 2
"""
```

## ADR (Architecture Decision Records)

Use for any significant technical decision:
- Technology choices
- Pattern selections
- Trade-off resolutions

Template: `docs/adr/0000-template.md`

## Research Documentation

Experiments in `experiments/` must include:
- Hypothesis
- Methodology
- Results (including negative results)
- References to relevant papers
- Date and author

## Review Checklist

Before merging, verify:
- [ ] Public APIs have docstrings
- [ ] Architecture changes have updated diagrams
- [ ] New agents documented in system-components.md
- [ ] Breaking changes noted in commit message
