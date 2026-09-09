"""The API process serves the built frontend.

One process and one origin is what removes the web server, the CORS
configuration and the SPA fallback rule from a deployment. These tests pin the
three things that make that safe: the API always wins, an unknown API path
still answers as an API, and no path can escape the build directory.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from frameworks_drivers.main import create_app
from infrastructure.config.settings import Settings

INDEX_HTML = "<!doctype html><html><body>NanoVox</body></html>"


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    """A minimal build: an index and one hashed asset."""
    build = tmp_path / "dist"
    (build / "assets").mkdir(parents=True)
    (build / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (build / "assets" / "index-abc123.js").write_text("console.log(1)", encoding="utf-8")
    # A file that must never be reachable from outside the build.
    (tmp_path / "secret.env").write_text("OPENAI_API_KEY=sk-do-not-serve", encoding="utf-8")
    return build


@pytest.fixture
def client(dist: Path, settings: Settings, schema: None) -> Iterator[TestClient]:
    """A started application serving ``dist``, over an isolated database.

    ``settings`` and ``schema`` come from the root conftest: a database in this
    test's own tmp_path, with the application's tables created in it. Both are
    needed even though nothing here reads the database -- entering
    ``TestClient`` runs the lifespan, and that releases abandoned runs, which
    queries ``analysis_runs``.

    Built with ``make_settings`` alone, these tests left ``database_url`` at its
    default and opened ``Data/nanovox.db``. That is a real file on a developer's
    machine, so they passed locally; in CI the file is absent (it is
    gitignored), SQLite obligingly created an empty one, and every test in this
    module failed on a missing table.
    """
    app = create_app(settings.model_copy(update={"frontend_dist_path": dist}))
    with TestClient(app) as test_client:
        yield test_client


class TestServingTheApp:
    def test_the_root_returns_the_app(self, client: TestClient) -> None:
        response = client.get("/")

        assert response.status_code == 200
        assert "NanoVox" in response.text

    @pytest.mark.parametrize("route", ["/calls", "/brokers", "/corpus", "/calls/42"])
    def test_a_client_side_route_returns_the_app(self, client: TestClient, route: str) -> None:
        # These have no file behind them; the app reads the path once loaded.
        # Without this a refresh on /calls would 404.
        response = client.get(route)

        assert response.status_code == 200
        assert "NanoVox" in response.text

    def test_a_real_asset_is_served_as_itself(self, client: TestClient) -> None:
        response = client.get("/assets/index-abc123.js")

        assert response.status_code == 200
        assert "console.log" in response.text

    def test_index_is_not_cached_but_assets_are(self, client: TestClient) -> None:
        # Asset names are content-hashed, so they are safe to cache forever.
        # index.html must not be, or a client keeps loading the old build.
        assert "no-store" in client.get("/").headers["cache-control"]
        assert "max-age=31536000" in client.get("/assets/index-abc123.js").headers["cache-control"]


class TestTheApiStillWins:
    def test_an_api_route_is_not_shadowed(self, client: TestClient) -> None:
        response = client.get("/api/v1/health")

        assert response.headers["content-type"].startswith("application/json")

    def test_an_unknown_api_path_answers_as_an_api(self, client: TestClient) -> None:
        """404 as JSON, not a page of HTML.

        The catch-all would otherwise hand a mistyped endpoint an HTML document,
        which a client's JSON parser reports as a syntax error — sending whoever
        debugs it looking in entirely the wrong place.
        """
        response = client.get("/api/v1/no-such-endpoint")

        assert response.status_code == 404
        assert "html" not in response.headers["content-type"]


class TestContainment:
    @pytest.mark.parametrize(
        "path",
        ["/../secret.env", "/assets/../../secret.env", "/%2e%2e/secret.env"],
    )
    def test_no_path_escapes_the_build_directory(self, client: TestClient, path: str) -> None:
        # The request path is attacker-controlled. Traversal must not serve a
        # file outside the build; falling back to the app is the safe answer.
        response = client.get(path)

        assert "sk-do-not-serve" not in response.text


class TestWithoutABuild:
    def test_the_api_runs_with_no_frontend_present(
        self, tmp_path: Path, settings: Settings, schema: None
    ) -> None:
        # The development arrangement: Vite serves the frontend on its own port,
        # and the absence of a build here is normal rather than a failure.
        #
        # Isolated settings for the same reason the fixture above uses them:
        # starting the app touches the database whether or not this test does.
        app = create_app(settings.model_copy(update={"frontend_dist_path": tmp_path / "absent"}))

        with TestClient(app) as client:
            assert client.get("/api/v1/health").status_code in {200, 503}
            assert client.get("/calls").status_code == 404
