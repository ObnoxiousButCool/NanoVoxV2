"""The corpus endpoints over HTTP, including the live progress stream.

The model is stubbed at the container boundary, so these tests exercise the real
routes, the real background runner and the real SSE channel without calling a
model. What they are checking is the contract the Corpus screen is built against.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from application.ports.llm_provider import LLMProvider, LlmRequest, StructuredResult, TModel
from domain.errors import NotFoundError
from frameworks_drivers.container import Container
from infrastructure.config.settings import Settings
from tests.support.analysis import ScriptedLayerProvider
from tests.support.settings import make_settings

CORPUS_SIZE = 3
CORPUS = "/api/v1/corpus"
RUNS = f"{CORPUS}/runs"
ANALYSES = f"{CORPUS}/analyses"

TRANSCRIPT = (
    "Agent Brad: Choice Administrators, Brad.\n"
    "Member: Hello. I wanted to ask what my emergency room copay is.\n"
    "Agent Brad: ER copay is $250, waived if you're admitted.\n"
    "Member: Two hundred and fifty. That's a lot.\n"
    "Agent Brad: That's the plan rate.\n"
    "Member: I've had this pressure in my chest since last night.\n"
    "Agent Brad: Yeah, urgent care is cheaper if you want to go that route.\n"
    "Member: Urgent care might be better then.\n"
    "Agent Brad: Urgent care can handle most things. There's one on Ridgeway if you're nearby.\n"
)


@pytest.fixture
def corpus_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "corpus"
    directory.mkdir()
    for number in range(1, CORPUS_SIZE + 1):
        (directory / f"call_{number:03d}.md").write_text(
            f"# Call #{number} — Fixture call {number}\n\n"
            "- **Agent:** Brad\n"
            "- **Score:** 36/100\n\n"
            f"## Transcript\n\n{TRANSCRIPT}\n"
            "## AI Insights Panel — NanoVox 5-Layer Output\n\nL3 — Agent Score: 36/100.\n",
            encoding="utf-8",
        )
    return directory


@pytest.fixture
def settings(tmp_path: Path, corpus_dir: Path) -> Settings:
    """Overrides the shared fixture to point at a small, local corpus."""
    return make_settings(
        app_env="local",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}",
        log_enabled=False,
        log_to_console=False,
        log_dir=tmp_path / "logs",
        corpus_path=corpus_dir,
        corpus_glob="call_*.md",
    )


class GatedProvider(ScriptedLayerProvider):
    """A scripted provider that waits for the test before answering.

    Lets a test observe a run *while it is working* without sleeping for a
    guessed interval. The wait yields to the event loop on every turn, so the
    request handling the SSE stream still runs.
    """

    gate = threading.Event()

    async def complete(self, request: LlmRequest[TModel]) -> StructuredResult[TModel]:
        # A polled threading.Event rather than an asyncio.Event, which ASYNC110
        # would prefer: the gate is released from the test's own thread, and
        # asyncio.Event is not safe to set from outside the loop's thread. The
        # sleep yields, so the request serving the stream still runs.
        while not GatedProvider.gate.is_set():  # noqa: ASYNC110
            await asyncio.sleep(0.01)
        return await super().complete(request)


@pytest.fixture(autouse=True)
def scripted_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every provider the API builds is the scripted one."""
    GatedProvider.gate.set()

    def create(self: Container, name: str | None = None, model: str | None = None) -> LLMProvider:
        return GatedProvider()

    monkeypatch.setattr(Container, "create_provider", create)


@pytest.fixture
def client(app: FastAPI, scripted_provider: None) -> Iterator[TestClient]:
    """Overrides the shared client to let any gated run finish before shutdown.

    A test that leaves a worker parked on the gate would otherwise have it
    cancelled mid-query as the application closes, which surfaces as a database
    error from a thread rather than as the test failure it is not.
    """
    with TestClient(app) as test_client:
        try:
            yield test_client
        finally:
            GatedProvider.gate.set()
            active = test_client.get(CORPUS).json()["active_run_id"]
            if active is not None:
                drain(test_client, active)


def post(client: TestClient, path: str, **body: Any) -> Any:
    return client.post(path, json=body)


def start(client: TestClient, **body: Any) -> dict[str, Any]:
    response = post(client, RUNS, **body)
    assert response.status_code == 201, response.text
    payload = response.json()
    assert isinstance(payload, dict)
    return payload


def drain(client: TestClient, run_id: int) -> None:
    """Block until the background task has settled the run.

    The stream is the mechanism rather than a poll loop with a sleep: it ends
    exactly when the run does.
    """
    with client.stream("GET", f"{RUNS}/{run_id}/stream") as response:
        assert response.status_code == 200
        for _ in response.iter_lines():
            pass


def wait_for_finish(client: TestClient, run_id: int) -> dict[str, Any]:
    drain(client, run_id)
    body = client.get(f"{RUNS}/{run_id}").json()
    assert isinstance(body, dict)
    return body


@contextmanager
def released_once_watching(app: FastAPI) -> Iterator[None]:
    """Let the parked worker finish once the stream is actually listening.

    This TestClient does not hand back a streaming response until the ASGI call
    has completed, so a stream on a run that never ends never returns — and the
    thread inside ``client.stream`` cannot release the gate itself. Something
    outside it has to.

    Keyed on the subscription rather than on a delay: the release happens after
    the endpoint has read the run and opened its subscription, so the snapshot is
    still taken mid-run and the assertion cannot flake on a slow machine.
    """
    bus = app.state.container.events

    def release() -> None:
        # Only this one stream is ever open in these tests, so a subscriber at
        # all is this subscriber.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and bus.subscriber_count == 0:
            time.sleep(0.01)
        GatedProvider.gate.set()

    watcher = threading.Thread(target=release, daemon=True)
    watcher.start()
    try:
        yield
    finally:
        GatedProvider.gate.set()
        watcher.join(timeout=5)


class TestCorpusStatus:
    def test_it_reports_the_corpus_before_anything_is_analysed(self, client: TestClient) -> None:
        body = client.get(CORPUS).json()

        assert body["total_calls"] == CORPUS_SIZE
        assert body["analysed_calls"] == 0
        assert body["outstanding"] == CORPUS_SIZE
        assert body["active_run_id"] is None

    def test_it_names_where_the_corpus_came_from(self, client: TestClient) -> None:
        # A run that read the wrong directory is otherwise invisible.
        assert "call_*.md" in client.get(CORPUS).json()["location"]


class TestStartingARun:
    def test_a_run_starts_with_one_pending_item_per_call(self, client: TestClient) -> None:
        GatedProvider.gate.clear()
        body = start(client)

        assert body["status"] in {"PENDING", "RUNNING"}
        assert body["progress"]["total"] == CORPUS_SIZE
        assert len(body["items"]) == CORPUS_SIZE
        assert body["items"][0]["reference"] == "C0001"

    def test_the_run_analyses_every_call(self, client: TestClient) -> None:
        body = wait_for_finish(client, start(client)["id"])

        assert body["status"] == "COMPLETED"
        assert body["progress"]["completed"] == CORPUS_SIZE
        assert body["progress"]["percent_complete"] == 100.0

    def test_the_analysed_calls_reach_the_dashboard(self, client: TestClient) -> None:
        # The point of the run: the corpus becomes the dashboard's data.
        wait_for_finish(client, start(client)["id"])

        overview = client.get("/api/v1/dashboard/overview").json()
        assert overview["metrics"]["total_calls"] == CORPUS_SIZE

    def test_a_second_run_is_refused_while_one_is_working(self, client: TestClient) -> None:
        GatedProvider.gate.clear()
        start(client)

        response = post(client, RUNS)

        assert response.status_code == 409
        assert "already in progress" in response.json()["title"]

    def test_an_unknown_provider_is_rejected_before_a_run_exists(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The provider is built first precisely so this is a 404 on the request
        # rather than a run that exists only to fail on its first call.
        def refuse(
            self: Container, name: str | None = None, model: str | None = None
        ) -> LLMProvider:
            raise NotFoundError("Unknown model provider: 'nope'.")

        monkeypatch.setattr(Container, "create_provider", refuse)

        response = post(client, RUNS, provider="nope")

        assert response.status_code == 404
        assert client.get(RUNS).json() == []


class TestCostGuard:
    def test_a_paid_provider_is_refused_without_an_acknowledgement(
        self, client: TestClient
    ) -> None:
        # Enforced by the API, not drawn in the UI: a dialog the server does not
        # require is decoration, and any other client would spend the money.
        response = post(client, RUNS, provider="openai")

        assert response.status_code == 400
        assert "paid provider" in response.json()["title"]
        assert client.get(RUNS).json() == []

    def test_an_acknowledged_paid_run_is_allowed(self, client: TestClient) -> None:
        response = post(client, RUNS, provider="openai", acknowledge_cost=True)

        assert response.status_code == 201

    def test_a_local_provider_needs_no_acknowledgement(self, client: TestClient) -> None:
        assert post(client, RUNS, provider="ollama").status_code == 201

    def test_providers_declare_whether_they_cost_money(self, client: TestClient) -> None:
        # The screen cannot warn about a cost it cannot see.
        providers = {
            item["name"]: item for item in client.get("/api/v1/providers").json()["providers"]
        }

        assert providers["ollama"]["billable"] is False
        assert providers["openai"]["billable"] is True
        assert providers["anthropic"]["billable"] is True


class TestIdempotencyOverHttp:
    def test_a_second_run_skips_what_is_already_analysed(self, client: TestClient) -> None:
        wait_for_finish(client, start(client)["id"])

        second = wait_for_finish(client, start(client)["id"])

        assert second["progress"]["skipped"] == CORPUS_SIZE
        assert second["progress"]["completed"] == 0
        assert "Already analysed" in second["items"][0]["message"]

    def test_forcing_re_analyses_every_call(self, client: TestClient) -> None:
        wait_for_finish(client, start(client)["id"])

        second = wait_for_finish(client, start(client, force=True)["id"])

        assert second["progress"]["completed"] == CORPUS_SIZE
        assert client.get(CORPUS).json()["analysed_calls"] == CORPUS_SIZE


class TestCancelAndResume:
    def test_cancelling_stops_the_run(self, client: TestClient) -> None:
        GatedProvider.gate.clear()
        run_id = start(client)["id"]

        cancelled = client.post(f"{RUNS}/{run_id}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "CANCELLING"

        GatedProvider.gate.set()
        body = wait_for_finish(client, run_id)
        assert body["status"] == "CANCELLED"

    def test_a_cancelled_run_can_be_resumed_to_completion(self, client: TestClient) -> None:
        GatedProvider.gate.clear()
        run_id = start(client)["id"]
        client.post(f"{RUNS}/{run_id}/cancel")
        GatedProvider.gate.set()
        wait_for_finish(client, run_id)

        resumed = client.post(f"{RUNS}/{run_id}/resume")
        assert resumed.status_code == 200
        assert resumed.json()["status"] in {"PENDING", "RUNNING"}

        body = wait_for_finish(client, run_id)
        assert body["status"] == "COMPLETED"
        assert body["progress"]["completed"] == CORPUS_SIZE

    def test_a_finished_run_cannot_be_cancelled(self, client: TestClient) -> None:
        run_id = start(client)["id"]
        wait_for_finish(client, run_id)

        response = client.post(f"{RUNS}/{run_id}/cancel")

        assert response.status_code == 409

    def test_a_completed_run_cannot_be_resumed(self, client: TestClient) -> None:
        run_id = start(client)["id"]
        wait_for_finish(client, run_id)

        response = client.post(f"{RUNS}/{run_id}/resume")

        assert response.status_code == 409
        assert "nothing left to do" in response.json()["title"]

    def test_cancelling_a_run_that_does_not_exist_is_a_404(self, client: TestClient) -> None:
        assert client.post(f"{RUNS}/4242/cancel").status_code == 404


class TestClearingTheCorpus:
    def test_it_removes_every_analysed_call_and_run(self, client: TestClient) -> None:
        run_id = start(client)["id"]
        wait_for_finish(client, run_id)
        assert client.get(CORPUS).json()["analysed_calls"] == CORPUS_SIZE

        response = client.delete(ANALYSES)

        assert response.status_code == 200
        assert response.json()["calls"] == CORPUS_SIZE
        assert response.json()["runs"] == 1
        assert client.get(CORPUS).json()["analysed_calls"] == 0
        assert client.get(RUNS).json() == []

    def test_the_corpus_itself_is_untouched(self, client: TestClient) -> None:
        # Clearing empties the database, not the folder of transcripts.
        run_id = start(client)["id"]
        wait_for_finish(client, run_id)

        client.delete(ANALYSES)

        body = client.get(CORPUS).json()
        assert body["total_calls"] == CORPUS_SIZE
        assert body["outstanding"] == CORPUS_SIZE

    def test_it_is_refused_while_a_run_is_working(self, client: TestClient) -> None:
        # The worker is mid-write; deleting under it would race.
        GatedProvider.gate.clear()
        run_id = start(client)["id"]

        response = client.delete(ANALYSES)

        assert response.status_code == 409
        GatedProvider.gate.set()
        wait_for_finish(client, run_id)

    def test_clearing_an_empty_corpus_is_not_an_error(self, client: TestClient) -> None:
        # The button must not punish a second press.
        response = client.delete(ANALYSES)

        assert response.status_code == 200
        assert response.json() == {"calls": 0, "runs": 0, "ground_truth_kept": True}


class TestReadingRuns:
    def test_an_unknown_run_is_a_404(self, client: TestClient) -> None:
        assert client.get(f"{RUNS}/4242").status_code == 404

    def test_the_list_is_newest_first_and_carries_no_items(self, client: TestClient) -> None:
        # A hundred items per run, twenty runs, is not a list payload.
        first = start(client)["id"]
        wait_for_finish(client, first)
        second = start(client)["id"]
        wait_for_finish(client, second)

        body = client.get(RUNS).json()

        assert [run["id"] for run in body] == [second, first]
        assert "items" not in body[0]

    def test_a_run_carries_its_provider_and_model(self, client: TestClient) -> None:
        # Provenance: which model produced these hundred calls.
        run_id = start(client)["id"]

        body = client.get(f"{RUNS}/{run_id}").json()

        assert body["provider"] == "scripted"
        assert body["model"] == "scripted-model"


class TestProgressStream:
    def test_it_opens_with_a_snapshot_so_a_late_client_is_not_blank(
        self, client: TestClient, app: FastAPI
    ) -> None:
        # Attaching halfway through would otherwise show nothing until the next
        # call finished — minutes of apparently broken screen.
        GatedProvider.gate.clear()
        run_id = start(client)["id"]

        with (
            released_once_watching(app),
            client.stream("GET", f"{RUNS}/{run_id}/stream") as response,
        ):
            assert response.headers["content-type"].startswith("text/event-stream")
            first = read_event(response.iter_lines())

        assert first["kind"] == "snapshot"
        assert first["progress"]["total"] == CORPUS_SIZE

    def test_the_snapshot_carries_the_whole_state_not_a_delta(
        self, client: TestClient, app: FastAPI
    ) -> None:
        # A client that reconnects mid-run rebuilds everything from this one
        # frame, so it has to be complete on its own.
        GatedProvider.gate.clear()
        run_id = start(client)["id"]

        with (
            released_once_watching(app),
            client.stream("GET", f"{RUNS}/{run_id}/stream") as response,
        ):
            snapshot = read_event(response.iter_lines())

        assert snapshot["run_id"] == run_id
        assert snapshot["run_status"] in {"PENDING", "RUNNING"}
        assert set(snapshot["progress"]) >= {"total", "completed", "failed", "percent_complete"}

    def test_a_finished_run_sends_its_state_and_closes(self, client: TestClient) -> None:
        # Holding a socket open on a run that ended before anyone connected is
        # not kindness.
        run_id = start(client)["id"]
        wait_for_finish(client, run_id)

        with client.stream("GET", f"{RUNS}/{run_id}/stream") as response:
            payloads = list(read_events(response.iter_lines()))

        assert len(payloads) == 1
        assert payloads[0]["kind"] == "snapshot"
        assert payloads[0]["run_status"] == "COMPLETED"

    def test_streaming_an_unknown_run_is_a_404_not_a_silent_socket(
        self, client: TestClient
    ) -> None:
        assert client.get(f"{RUNS}/4242/stream").status_code == 404


def read_event(lines: Iterator[str]) -> dict[str, Any]:
    """Read one SSE frame, skipping heartbeats."""
    for line in lines:
        if line.startswith("data:"):
            payload = json.loads(line[len("data:") :].strip())
            assert isinstance(payload, dict)
            return payload
    raise AssertionError("The stream ended before an event arrived.")


def read_events(lines: Iterator[str]) -> Iterator[dict[str, Any]]:
    for line in lines:
        if line.startswith("data:"):
            payload = json.loads(line[len("data:") :].strip())
            assert isinstance(payload, dict)
            yield payload


class TestResumeIsAtomic:
    def test_a_provider_that_cannot_be_built_leaves_the_run_untouched(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Returning the run to PENDING and *then* failing would leave it active
        # with no worker, blocking every future run.
        GatedProvider.gate.clear()
        run_id = start(client)["id"]
        client.post(f"{RUNS}/{run_id}/cancel")
        GatedProvider.gate.set()
        wait_for_finish(client, run_id)

        def refuse(
            self: Container, name: str | None = None, model: str | None = None
        ) -> LLMProvider:
            raise NotFoundError("Unknown model provider: 'gone'.")

        monkeypatch.setattr(Container, "create_provider", refuse)

        assert client.post(f"{RUNS}/{run_id}/resume").status_code == 404

        after = client.get(f"{RUNS}/{run_id}").json()
        assert after["status"] == "CANCELLED"
        assert after["can_resume"] is True
        assert client.get(CORPUS).json()["active_run_id"] is None
