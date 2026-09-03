"""Reads the corpus from authored markdown files.

Each file holds a transcript and, below it, the panel a human wrote about that
call. Both are parsed; they are kept in separate fields and never merged, because
the whole point of DEC-01 is that the model re-derives its own conclusions and is
then measured against the authored ones.

The parser is strict about the transcript and forgiving about the panel. A
missing transcript makes the file unusable and must fail loudly; a missing
``Tier`` line costs one comparison in a later report and must not stop a run of a
hundred calls.
"""

from __future__ import annotations

import re
from pathlib import Path

from application.ports.corpus_source import CorpusSource
from domain.entities.corpus_call import CorpusCall
from domain.entities.ground_truth import GroundTruth
from domain.errors import ConfigurationError

TRANSCRIPT_HEADING = "## Transcript"
PANEL_HEADING = "## AI Insights Panel"

REFERENCE_PREFIX = "C"
REFERENCE_DIGITS = 4

# Matches a heading of the form: hash, Call, hash-number, dash, title. All three
# dash characters are listed because the corpus files use an em dash and a human
# editing one of them will reach for whichever their keyboard offers.
_HEADING = re.compile(r"^#\s*Call\s*#?(?P<number>\d+)\s*(?:[—–-]\s*(?P<title>.+))?$")  # noqa: RUF001
# Matches a metadata bullet: dash, bold key, colon, value.
_BULLET = re.compile(r"^-\s*\*\*(?P<key>[^:*]+):?\*\*:?\s*(?P<value>.*)$")
_MEMBER_CONTEXT = re.compile(r"^\*\*Member context:?\*\*:?\s*(?P<value>.*)$", re.IGNORECASE)
_LEADING_NUMBER = re.compile(r"^\s*(\d+)")

_SENTIMENT_SEPARATORS = ("→", "->", "»")
_DIGITS = re.compile(r"(\d+)")


def reference_for(number: int) -> str:
    """The call reference a corpus number maps to, e.g. 89 -> ``C0089``.

    Deterministic on purpose: it is what makes a run idempotent across processes
    without storing a mapping table.
    """
    return f"{REFERENCE_PREFIX}{number:0{REFERENCE_DIGITS}d}"


class MarkdownCorpusSource(CorpusSource):
    """Loads corpus calls from a directory of markdown files."""

    def __init__(self, directory: Path, glob: str) -> None:
        self._directory = directory
        self._glob = glob

    def describe(self) -> str:
        return f"{self._directory} ({self._glob})"

    def load(self) -> tuple[CorpusCall, ...]:
        if not self._directory.is_dir():
            raise ConfigurationError(
                "The call corpus directory does not exist.",
                detail=f"CORPUS_PATH points at {self._directory}, which is not a directory.",
            )

        paths = sorted(self._directory.glob(self._glob))
        if not paths:
            raise ConfigurationError(
                "The call corpus is empty.",
                detail=(
                    f"No files matching {self._glob!r} in {self._directory}. "
                    "A run against an empty corpus would report success having done nothing."
                ),
            )

        calls = [parse_corpus_file(path.read_text(encoding="utf-8"), path.stem) for path in paths]
        _reject_duplicate_references(calls)
        return tuple(sorted(calls, key=lambda call: call.sequence))


def _reject_duplicate_references(calls: list[CorpusCall]) -> None:
    """Two files claiming one call number would silently analyse only one of them."""
    seen: dict[str, str] = {}
    for call in calls:
        clash = seen.get(call.reference)
        if clash is not None:
            raise ConfigurationError(
                f"Two corpus files claim call reference {call.reference}.",
                detail=f"{clash} and {call.source_id} both parse to the same call number.",
            )
        seen[call.reference] = call.source_id


def parse_corpus_file(text: str, source_id: str) -> CorpusCall:
    """Parse one corpus file into a call plus its authored panel."""
    header, transcript, panel = _split_sections(text, source_id)
    number, title = _parse_heading(header, source_id)
    fields = _parse_fields(header)

    return CorpusCall(
        source_id=source_id,
        reference=reference_for(number),
        title=title,
        transcript=transcript,
        duration_minutes=_minutes(fields.get("duration")),
        ground_truth=_ground_truth(fields, panel),
        sequence=number,
    )


def _split_sections(text: str, source_id: str) -> tuple[str, str, str]:
    """Cut the file into header, transcript and panel."""
    lines = text.splitlines()
    transcript_at = _heading_index(lines, TRANSCRIPT_HEADING)
    if transcript_at is None:
        raise ConfigurationError(
            f"Corpus file {source_id!r} has no transcript.",
            detail=f"Expected a {TRANSCRIPT_HEADING!r} heading.",
        )

    panel_at = _heading_index(lines, PANEL_HEADING, start=transcript_at + 1)
    end = panel_at if panel_at is not None else len(lines)

    header = "\n".join(lines[:transcript_at])
    transcript = "\n".join(lines[transcript_at + 1 : end]).strip()
    panel = "\n".join(lines[panel_at + 1 :]).strip() if panel_at is not None else ""
    return header, transcript, panel


def _heading_index(lines: list[str], heading: str, *, start: int = 0) -> int | None:
    for index in range(start, len(lines)):
        if lines[index].strip().startswith(heading):
            return index
    return None


def _parse_heading(header: str, source_id: str) -> tuple[int, str]:
    """Read the call number and title from the ``# Call #N — Title`` line."""
    for line in header.splitlines():
        match = _HEADING.match(line.strip())
        if match:
            title = (match.group("title") or "").strip()
            return int(match.group("number")), title or f"Call {match.group('number')}"

    # Fall back to the filename so a file with a malformed heading is still
    # analysable — the number is the identity, and the filename carries it too.
    digits = _DIGITS.search(source_id)
    if digits is None:
        raise ConfigurationError(
            f"Corpus file {source_id!r} has no call number.",
            detail="Expected a '# Call #N' heading or a number in the filename.",
        )
    return int(digits.group(1)), source_id


def _parse_fields(header: str) -> dict[str, str]:
    """Collect the ``- **Key:** value`` bullets, plus the member context line.

    Repeated keys accumulate: ``Broker Signal`` appears more than once in some
    files, and keeping only the last would drop a named broker.
    """
    fields: dict[str, str] = {}
    for raw in header.splitlines():
        line = raw.strip()
        bullet = _BULLET.match(line)
        if bullet:
            key = bullet.group("key").strip().lower()
            value = bullet.group("value").strip()
            fields[key] = f"{fields[key]}\n{value}" if key in fields else value
            continue
        context = _MEMBER_CONTEXT.match(line)
        if context:
            fields["member context"] = context.group("value").strip()
    return fields


def _ground_truth(fields: dict[str, str], panel: str) -> GroundTruth:
    start, end = _sentiment_arc(fields.get("sentiment arc", ""))
    return GroundTruth(
        agent_name=fields.get("agent") or None,
        tier=_upper(fields.get("tier")),
        score=_score(fields.get("score")),
        resolution=_upper(fields.get("resolution")),
        sentiment_start=start,
        sentiment_end=end,
        topics=_list(fields.get("topics", "")),
        broker_names=_broker_names(fields.get("broker signal", "")),
        member_context=fields.get("member context") or None,
        panel_text=panel,
    )


def _minutes(value: str | None) -> int | None:
    """Read ``~11 min`` as 11, and anything unparseable as "not stated".

    Forgiving like the rest of the panel parsing: the corpus writes "~11 min",
    "11 min" and "11 minutes" interchangeably, and a duration nobody can read is
    one missing figure rather than a reason to fail a hundred-call run.
    """
    if not value:
        return None
    match = _DIGITS.search(value)
    if match is None:
        return None
    minutes = int(match.group(1))
    # A zero or negative duration is not a measurement. Treated as absent so it
    # cannot drag a median down or make a call look instantly resolved.
    return minutes if minutes > 0 else None


def _upper(value: str | None) -> str | None:
    return value.strip().upper() if value and value.strip() else None


def _score(value: str | None) -> int | None:
    """Read ``36/100`` as 36, and anything unparseable as "not stated"."""
    if not value:
        return None
    match = _LEADING_NUMBER.match(value)
    if match is None:
        return None
    score = int(match.group(1))
    return score if 0 <= score <= 100 else None


def _sentiment_arc(value: str) -> tuple[str | None, str | None]:
    for separator in _SENTIMENT_SEPARATORS:
        if separator in value:
            start, _, end = value.partition(separator)
            return _upper(start), _upper(end)
    return (_upper(value), None) if value.strip() else (None, None)


def _list(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _broker_names(value: str) -> tuple[str, ...]:
    """Names from ``Anthony Salerno: failed to explain ...`` lines, in order.

    Only the part before the colon is a name; the rest is the author's account of
    what went wrong, which belongs to the panel text rather than to a name list.
    """
    names: list[str] = []
    for line in value.splitlines():
        name, separator, _ = line.partition(":")
        candidate = (name if separator else line).strip()
        if candidate and candidate not in names:
            names.append(candidate)
    return tuple(names)
