# Python Coding Standards

> Enforced via ruff, mypy, and pre-commit hooks.

---

## Language & Runtime

- Python 3.11+ required
- Use `from __future__ import annotations` in all modules
- Type annotations on all public functions and methods

## Style

- Line length: 100 characters (enforced by ruff)
- Quotes: double quotes (enforced by ruff format)
- Indent: 4 spaces
- Imports: sorted by isort (stdlib → third-party → first-party)

## Naming

| Element | Convention | Example |
|---------|-----------|---------|
| Module | snake_case | `chromosome_agent.py` |
| Class | PascalCase | `BaseAgent` |
| Function/method | snake_case | `execute_task()` |
| Constant | UPPER_SNAKE | `MAX_RETRIES` |
| Type variable | PascalCase | `AgentT` |
| Private | leading underscore | `_internal_method()` |

## Type Annotations

```python
# Required for all public APIs
def execute(self, state: SwarmState) -> SwarmState: ...

# Use | for unions (Python 3.11+)
def get_result(self) -> AgentResult | None: ...

# Use generics
def filter_variants(variants: list[VariantRecord]) -> list[VariantRecord]: ...
```

## Dataclasses & Models

- Use `@dataclass` for internal data structures
- Use `@dataclass(frozen=True)` for immutable messages
- Use `TypedDict` for LangGraph state compatibility
- Use `Enum` for fixed sets of values

## Error Handling

- Never silently swallow exceptions
- Append errors to state rather than raising (LangGraph compatibility)
- Use specific exception types, not bare `except`
- Log errors with agent_id and correlation_id for tracing

## Docstrings

- Required on all public classes, methods, and modules
- Use Google-style docstrings
- Include `Future:` section for planned functionality

```python
def execute(self, state: SwarmState) -> SwarmState:
    """Execute the agent's core logic.

    Args:
        state: Current execution state from the DAG.

    Returns:
        Updated state dict with this agent's contributions.

    Future:
        Will integrate with MCP tools for database access.
    """
```

## Agent-Specific Rules

- All agents inherit from `BaseAgent`
- Agents must declare `agent_type` and `execution_mode`
- Deterministic agents must produce identical output for identical input
- Generative agents must include confidence scores and source attribution
- Every agent result must pass `validate_output()` before submission
