import pytest


@pytest.fixture(autouse=True)
def _media_tmp(settings, tmp_path):
    """Keep uploaded test files out of the real media directory."""
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture(autouse=True)
def _clear_cache():
    """Reset the cache between tests so allauth rate limits don't leak."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()
