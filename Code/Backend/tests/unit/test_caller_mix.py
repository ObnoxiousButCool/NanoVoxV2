"""Who calls, and how differently each of them fares."""

from __future__ import annotations

from domain.aggregation.caller_mix import CallerCall, caller_mix

KNOWN = ("MEMBER", "EMPLOYER", "BROKER")


def call(
    caller: str | None, resolution: str = "RESOLVED", score: int = 80, seconds: int = 420
) -> CallerCall:
    return CallerCall(
        caller_type=caller, resolution=resolution, score=score, duration_seconds=seconds
    )


class TestTheBreakdown:
    def test_each_population_is_measured_separately(self) -> None:
        result = caller_mix(
            [
                call("MEMBER", "RESOLVED"),
                call("MEMBER", "UNRESOLVED"),
                call("EMPLOYER", "RESOLVED"),
            ],
            known_types=KNOWN,
        )
        by_type = {row.caller_type: row for row in result.callers}

        assert by_type["MEMBER"].resolution_rate == 50.0
        assert by_type["EMPLOYER"].resolution_rate == 100.0

    def test_partially_resolved_is_not_resolved(self) -> None:
        result = caller_mix([call("MEMBER", "PARTIALLY RESOLVED")], known_types=KNOWN)

        assert result.callers[0].resolution_rate == 0.0

    def test_the_largest_population_comes_first(self) -> None:
        result = caller_mix(
            [call("BROKER"), call("MEMBER"), call("MEMBER")],
            known_types=KNOWN,
        )

        assert result.callers[0].caller_type == "MEMBER"
        assert result.callers[0].share == 66.7

    def test_handle_time_is_absent_where_no_call_states_one(self) -> None:
        result = caller_mix(
            [
                CallerCall(
                    caller_type="MEMBER",
                    resolution="RESOLVED",
                    score=80,
                    duration_seconds=None,
                )
            ],
            known_types=KNOWN,
        )

        assert result.callers[0].average_handle_minutes is None


class TestPopulationsThatDidNotCall:
    def test_a_configured_caller_with_no_calls_still_gets_a_row(self) -> None:
        # A population nobody heard from is a finding. A row that vanishes
        # cannot be noticed.
        result = caller_mix([call("MEMBER")], known_types=KNOWN)
        by_type = {row.caller_type: row for row in result.callers}

        assert set(by_type) == set(KNOWN)
        assert by_type["BROKER"].calls == 0
        assert by_type["BROKER"].average_handle_minutes is None


class TestWhatCannotBeAttributed:
    def test_a_call_stating_no_caller_is_counted_aside(self) -> None:
        # A fourth bar labelled "unknown" invites reading it as a fourth
        # population, which it is not — it is a gap in the source.
        result = caller_mix([call("MEMBER"), call(None)], known_types=KNOWN)

        assert result.unattributed_calls == 1
        assert result.total_calls == 1
        assert all(row.caller_type in KNOWN for row in result.callers)

    def test_a_caller_outside_the_vocabulary_still_appears(self) -> None:
        # The numbers have to add up to the calls that exist, even when the
        # configuration has fallen behind the data.
        result = caller_mix([call("MEMBER"), call("VENDOR")], known_types=KNOWN)
        by_type = {row.caller_type: row for row in result.callers}

        assert by_type["VENDOR"].calls == 1
        assert result.total_calls == 2

    def test_no_calls_at_all_is_not_an_error(self) -> None:
        result = caller_mix([], known_types=KNOWN)

        assert result.total_calls == 0
        assert all(row.calls == 0 for row in result.callers)
