import pathlib
import sys
import uuid
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.append(str(pathlib.Path(__file__).resolve().parents[2] / "server"))

from app.api.routes.search import router  # noqa: E402


class DummyAPIKeys:
    def enforce(self, tenant_id: str, api_key: str | None) -> None:  # noqa: D401 - simple stub
        return None


class DummyRateLimiter:
    def check(self, _: str) -> None:  # noqa: D401 - simple stub
        return None


class DummySearchCache:
    def get(self, _: tuple) -> None:  # noqa: D401 - simple stub
        return None

    def set(self, *args, **kwargs) -> None:  # noqa: D401 - simple stub
        return None


class DummyStats:
    def record_search(self, _: int) -> None:  # noqa: D401 - simple stub
        return None


class ExplodingSearcher:
    def __init__(self) -> None:
        self.default_alpha = 0.2
        self.default_beta = 0.8
        self.alpha = self.default_alpha
        self.beta = self.default_beta

    def search_with_debug(self, *_, alpha=None, beta=None, **__):  # noqa: D401 - simple stub
        if alpha is not None:
            self.alpha = alpha
        if beta is not None:
            self.beta = beta
        raise RuntimeError("variant boom")


@pytest.fixture
def app(monkeypatch):
    app = FastAPI()
    app.include_router(router)

    searcher = ExplodingSearcher()
    context = SimpleNamespace(
        searcher=searcher,
        search_cache=DummySearchCache(),
        api_keys=DummyAPIKeys(),
        rate_limiter=DummyRateLimiter(),
        stats=DummyStats(),
        reranker=None,
    )
    app.state.context = context

    monkeypatch.setenv("AB_VARIANT_ALPHA", "0.9")
    monkeypatch.setenv("AB_VARIANT_BETA", "0.1")

    fake_uuid = uuid.UUID(hex="0000000000000000000000000000000f")
    monkeypatch.setattr("app.api.routes.search.uuid.uuid4", lambda: fake_uuid)

    return app


def test_variant_weights_are_restored_after_failure(app):
    client = TestClient(app)
    searcher = app.state.context.searcher

    with pytest.raises(RuntimeError):
        client.post(
            "/v1/search",
            json={
                "tenant_id": "tenant",
                "repo_id": "repo",
                "query": "hello",
            },
        )

    assert searcher.alpha == pytest.approx(searcher.default_alpha)
    assert searcher.beta == pytest.approx(searcher.default_beta)
