"""pytest configuration for the hackathon test suite."""

import pytest


# Enable pytest-asyncio in the (default) auto mode for this directory
# only. The main repo's root pyproject.toml config is untouched.
def pytest_collection_modifyitems(config, items):
    """Auto-mark async test functions with asyncio."""
    for item in items:
        if isinstance(item, pytest.Function) and item.get_closest_marker("asyncio") is None:
            fn = item.function
            if hasattr(fn, "__code__") and fn.__code__.co_flags & 0x100:  # CO_COROUTINE
                item.add_marker(pytest.mark.asyncio)
