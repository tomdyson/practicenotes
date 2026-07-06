import pytest


@pytest.fixture(autouse=True)
def _clear_cache():
    """Reset the cache between tests so allauth rate limits don't leak."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()
