# Contributing to Anukriti Swarm

Thank you for your interest in contributing to Anukriti Swarm. This document provides guidelines for contributing to this research project.

---

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/anukriti-swarm.git`
3. Create a feature branch: `git checkout -b feat/your-feature`
4. Set up your environment:
   ```bash
   cp .env.example .env
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

## Development Workflow

### Branch Naming

| Prefix | Purpose |
|--------|---------|
| `feat/` | New features or agents |
| `fix/` | Bug fixes |
| `docs/` | Documentation changes |
| `refactor/` | Code restructuring |
| `experiment/` | Research experiments |

### Commit Messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

feat(agents): add population frequency lookup agent
fix(memory): resolve vector store connection timeout
docs(architecture): update data flow diagram
```

### Before Submitting

```bash
make format    # Auto-format code
make lint      # Check for issues
make test      # Run test suite
```

All checks must pass before a PR will be reviewed.

## Code Standards

- Python 3.11+ with type annotations
- Follow ruff linting rules (configured in pyproject.toml)
- Maximum line length: 100 characters
- All public functions require docstrings
- New agents must include unit tests

## Adding a New Agent

1. Create module in `agents/your_agent/`
2. Implement the base agent interface
3. Add tests in `tests/test_your_agent.py`
4. Document in `docs/agents/your_agent.md`
5. Update architecture diagrams if topology changes

## Research Contributions

For research experiments:
- Place experiments in `experiments/` with dated directories
- Include a README explaining hypothesis and methodology
- Log all results, including negative results
- Reference relevant papers in your documentation

## Pull Request Process

1. Ensure all tests pass
2. Update documentation for any interface changes
3. Add a clear PR description explaining what and why
4. Request review from at least one maintainer
5. Squash commits before merge if requested

## Code of Conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

---

*Questions? Open a discussion or reach out to the maintainers.*
