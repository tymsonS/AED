import types

from django.test import override_settings
from pytest_mock import MockerFixture

from mcod.core.api import middleware_loader


class FakeMiddleware1:
    def process_request(self, req, resp):
        pass


class FakeMiddleware2:
    def process_response(self, req, resp, resource, success):
        pass


class FakeMiddleware3:
    def process_resource(self, req, resp, resource, params):
        pass


@override_settings(
    FALCON_MIDDLEWARES=[
        "mcod.core.tests.test_middleware_loader.FakeMiddleware1",
        "mcod.core.tests.test_middleware_loader.FakeMiddleware2",
    ],
    ENABLE_CSRF=False,
    FALCON_CACHING_ENABLED=False,
)
def test_loaded_middleware_order():
    """
    Test that middleware defined in FALCON_MIDDLEWARES is loaded
    in the exact order it is listed, when no additional middlewares are enabled.
    """
    middlewares = middleware_loader.middleware_loader()
    assert len(middlewares) == 2
    assert isinstance(middlewares[0], FakeMiddleware1)
    assert isinstance(middlewares[1], FakeMiddleware2)


@override_settings(
    FALCON_MIDDLEWARES=["mcod.core.tests.test_middleware_loader.FakeMiddleware1"],
    ENABLE_CSRF=True,
    FALCON_CACHING_ENABLED=True,
)
def test_all_middlewares_enabled_and_ordered(mocker: MockerFixture):
    """
    Test that all supported middleware types (CSRF, limiter, caching)
    are loaded and appended in the correct order after base middleware
    when all feature flags are enabled.
    """
    mocker.patch(
        "mcod.core.api.middleware_loader.FALCON_CSRF_MIDDLEWARE",
        "mcod.core.tests.test_middleware_loader.FakeMiddleware2",
    )
    mocker.patch("mcod.core.api.middleware_loader.app_cache", types.SimpleNamespace(middleware=FakeMiddleware3()))
    middlewares = middleware_loader.middleware_loader()

    assert len(middlewares) == 3
    assert isinstance(middlewares[0], FakeMiddleware1)
    assert isinstance(middlewares[1], FakeMiddleware2)
    assert isinstance(middlewares[2], FakeMiddleware3)


@override_settings(
    FALCON_MIDDLEWARES=["mcod.core.tests.test_middleware_loader.FakeMiddleware1"],
    ENABLE_CSRF=True,
    FALCON_CACHING_ENABLED=False,
)
def test_csrf_is_last(mocker: MockerFixture):
    """
    Test that CSRF middleware is appended as the last item
    when only CSRF protection is enabled.
    """
    mocker.patch(
        "mcod.core.api.middleware_loader.FALCON_CSRF_MIDDLEWARE",
        "mcod.core.tests.test_middleware_loader.FakeMiddleware2",
    )
    middlewares = middleware_loader.middleware_loader()

    assert isinstance(middlewares[-1], FakeMiddleware2)


@override_settings(
    FALCON_MIDDLEWARES=["mcod.core.tests.test_middleware_loader.FakeMiddleware1"],
    ENABLE_CSRF=False,
    FALCON_CACHING_ENABLED=True,
)
def test_cache_is_last(mocker: MockerFixture):
    """
    Test that caching middleware is appended as the last item
    when only caching is enabled.
    """
    mocker.patch(
        "mcod.core.api.middleware_loader.app_cache",
        types.SimpleNamespace(middleware=FakeMiddleware3()),
    )

    middlewares = middleware_loader.middleware_loader()

    assert isinstance(middlewares[-1], FakeMiddleware3)


@override_settings(
    FALCON_MIDDLEWARES=[],
    ENABLE_CSRF=False,
    FALCON_CACHING_ENABLED=False,
)
def test_no_middleware_returns_empty_list():
    """Test that loader returns an empty list when no middleware is configured or enabled."""
    middlewares = middleware_loader.middleware_loader()
    assert middlewares == []
