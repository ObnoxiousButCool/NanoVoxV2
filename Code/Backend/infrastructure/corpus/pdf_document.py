"""Reading a call-corpus PDF into the markdown the pipeline already ingests.

This replaces the single multi-line regex that ``scripts/convert_corpus_pdf.py``
used to carry. That regex broke on every version of the corpus, and each time it
broke it broke *silently* — v5 converted at 82 of 100 calls and printed a success
line, and the 18 it dropped were the broker calls, the most valuable ones in the
document. The lesson was not "fix the regex" but "stop requiring a fixed number
of fixed-shape lines", because a PDF text layer will not give you one:

* **Titles wrap.** Three of v6's hundred headings run onto a second line, and so
  does one of its ``BROKER SIGNAL`` lines.
* **Page furniture lands mid-header.** The running head and a bare page number
  appear between a call's own lines wherever a page happens to break.
* **Fields come and go between versions.** v5 added ``BROKER SIGNAL``; v6 added
  ``REPEAT CONTACT``, dropped the end time, and appended a queue name.

So the parser is line-oriented and prefix-driven, the same way
:mod:`infrastructure.corpus.markdown_corpus` reads the files this produces: find
the headings, then read forward collecting fields by how they announce
themselves, letting anything unrecognised continue the field above it. A version
that adds a seventh field costs one entry in :data:`_FIELDS`, not a new grammar.

What is *not* forgiving is the count. Every ``Call #N`` heading in the document
must come out the other side as a call, and :func:`extract_calls` raises if one
does not. Being strict there is what makes it safe to be forgiving everywhere
else.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime, timedelta

from application.ports.corpus_document import CorpusDocumentReader, ImportedCall
from domain.errors import ValidationError

TRANSCRIPT_HEADING = "## Transcript"
PANEL_HEADING = "## AI Insights Panel"

# The panel heading as the PDF writes it, which marks the end of the transcript.
# Matched case-insensitively: v4 and v5 shout it, v6 writes "AI insights panel".
_PANEL_MARKER = re.compile(r"^\s*AI insights panel\b", re.IGNORECASE)

# A call starts here. The title on this line may be only its first half.
_HEADING = re.compile(r"^Call #(?P<number>\d+)\s*[—–-]\s*(?P<title>.*)$")  # noqa: RUF001

# "Tue 01 Sep 2026 · 08:52:00 · AHT 5m 31s · Platform & Forms", and the v4/v5
# form that carries an end time as well. The queue name is v6 only. Everything
# after the date is optional so a version that drops a part still parses.
_WHEN = re.compile(
    r"^\w{3}\s+(?P<date>\d{1,2}\s+\w{3}\s+\d{4})"
    # The corpus separates a time range with an en dash. Written as an escape
    # rather than marked noqa like the classes below, because that comment
    # would take this line past the length limit.
    r"(?:\s*·\s*(?P<start>\d{2}:\d{2}:\d{2})(?:\s*[\u2013-]\s*(?P<end>\d{2}:\d{2}:\d{2}))?)?"
    r"(?:\s*·\s*AHT\s+(?P<aht>[\dhms\s]+?))?"
    r"(?:\s*·\s*(?P<queue>[^·]+?))?\s*$"
)

# "MEMBER | POOR · 36/100 | UNRESOLVED | NEUTRAL → FRUSTRATED | Agent: Tiffany".
# The upper-case runs allow spaces: "PARTIALLY RESOLVED" and "CHURN RISK" are
# two words, and matching \w+ alone silently skips those calls.
_UPPER = r"[A-Z][A-Z ]*[A-Z]|[A-Z]+"
_STATUS = re.compile(
    rf"^(?P<caller>MEMBER|EMPLOYER|BROKER)\s*\|\s*(?P<tier>\w+)\s*·\s*(?P<score>\d+)/100"
    rf"\s*\|\s*(?P<resolution>{_UPPER})"
    rf"\s*\|\s*(?P<start_mood>{_UPPER})\s*→\s*(?P<end_mood>{_UPPER})"
    r"\s*\|\s*Agent:\s*(?P<agent>.+?)\s*$"
)

# Named header fields, by the prefix that announces them. The value is the key
# they are collected under; a version adding a field adds a line here.
_FIELDS: dict[str, re.Pattern[str]] = {
    "context": re.compile(r"^Context:\s*(?P<value>.*)$", re.IGNORECASE),
    "topics": re.compile(r"^Topics:\s*(?P<value>.*)$", re.IGNORECASE),
    "broker": re.compile(r"^BROKER SIGNAL\s*[—–-]?\s*(?P<value>.*)$"),  # noqa: RUF001
    "repeat": re.compile(r"^REPEAT CONTACT\s*[—–-]?\s*(?P<value>.*)$"),  # noqa: RUF001
}

# Page furniture: the running head, and a page number on a line of its own.
_RUNNING_HEAD = re.compile(r"^\s*Choice Administrators\s*[—–-]\s*Call Corpus", re.IGNORECASE)  # noqa: RUF001
_PAGE_NUMBER = re.compile(r"^\s*\d{1,3}\s*$")

# A transcript turn, which ends the header block whatever else is missing.
_TURN = re.compile(r"^\s*(?:Agent\s+\w+|Caller|Member|System|IVR)\s*:", re.IGNORECASE)

_AHT = re.compile(r"^(?:(?P<minutes>\d+)\s*m)?\s*(?:(?P<seconds>\d+)\s*s)?$")

# A broker signal written without a colon: "Marcus Trent named aloud by the
# caller". Eighteen of v6's twenty-six take this form and the other eight are
# "Name: what they did".
#
# The colon matters more than it looks. Everything downstream reads the broker's
# name as the text before it — so left alone, the Brokers screen lists a broker
# called "Marcus Trent named aloud by the caller", and the same person appears
# again under their real name from the eight that do carry one. A name is a
# leading run of capitalised words followed by a lower-case word, which is what
# separates "Marcus Trent named aloud" from "Positive signal — broker had...".
_BROKER_WITHOUT_COLON = re.compile(
    r"^(?P<name>[A-Z][\w'’.-]*(?:\s+[A-Z][\w'’.-]*){1,2})\s+(?P<note>[a-z].*)$"  # noqa: RUF001
)


def _normalise_broker(value: str | None) -> str | None:
    """A broker signal as ``Name: what they did``, whichever way it was written."""
    if not value or ":" in value:
        return value
    match = _BROKER_WITHOUT_COLON.match(value.strip())
    if match is None:
        return value
    return f"{match.group('name')}: {match.group('note')}"


def parse_handle_time(value: str) -> int | None:
    """``5m 21s`` as seconds, or None where it cannot be read.

    Forgiving rather than fatal: handle time drives the time analysis, but one
    unreadable value is one missing figure, not a reason to refuse a document
    the rest of which is fine.
    """
    match = _AHT.match(value.strip())
    if match is None or not (match.group("minutes") or match.group("seconds")):
        return None
    return int(match.group("minutes") or 0) * 60 + int(match.group("seconds") or 0)


def read_pdf(data: bytes) -> str:
    """The document's text layer, pages joined by newlines.

    Joined rather than kept per page because a call block straddles page breaks
    routinely, and the parser has to see its lines as consecutive.
    """
    import io

    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise ValidationError(
            "Reading PDF corpus documents needs pypdf.",
            detail="pip install -r Code/Backend/requirements.txt",
        ) from exc

    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        raise ValidationError(
            "That file could not be read as a PDF.",
            detail=str(exc),
        ) from exc


def _is_furniture(line: str) -> bool:
    return bool(_RUNNING_HEAD.match(line) or _PAGE_NUMBER.match(line))


def _clean(text: str) -> list[str]:
    """Document lines with page furniture removed.

    Dropped before parsing rather than skipped during it, because the running
    head and page number appear *between* a call's own header lines wherever a
    page breaks — and a parser that has to expect them everywhere is a parser
    that will accept them as field values somewhere.
    """
    return [line for line in text.splitlines() if line.strip() and not _is_furniture(line)]


def _end_from(start: str | None, handle_seconds: int | None, day: date | None) -> str | None:
    """The end time, derived where the document states only a start.

    v6 dropped the end time and kept handle time, so the end is recoverable
    exactly rather than guessed. Derived here rather than left absent because
    "when in the day did this call sit" is answered from the pair.
    """
    if start is None or handle_seconds is None or day is None:
        return None
    try:
        began = datetime.combine(day, datetime.strptime(start, "%H:%M:%S").time())  # noqa: DTZ007
    except ValueError:
        return None
    return (began + timedelta(seconds=handle_seconds)).strftime("%H:%M:%S")


class _Block:
    """One call's lines, read forward into fields."""

    def __init__(self, number: int, first_title_line: str) -> None:
        self.number = number
        self.title_parts = [first_title_line.strip()]
        self.when: re.Match[str] | None = None
        self.status: re.Match[str] | None = None
        self.fields: dict[str, list[str]] = {}
        self.last_field: str | None = None
        self.transcript: list[str] = []
        self.panel: list[str] = []

    def read(self, lines: list[str]) -> None:
        in_transcript = False
        in_panel = False

        for line in lines:
            if in_panel:
                self.panel.append(line)
                continue
            if _PANEL_MARKER.match(line):
                in_panel = True
                continue
            if in_transcript:
                self.transcript.append(line)
                continue

            # Still in the header block. Each named field wins over a
            # continuation, and a transcript turn ends the header outright.
            if self._take_field(line):
                continue
            if self.when is None and (match := _WHEN.match(line.strip())):
                self.when = match
                self.last_field = None
                continue
            if self.status is None and (match := _STATUS.match(line.strip())):
                self.status = match
                self.last_field = None
                continue
            if _TURN.match(line):
                in_transcript = True
                self.transcript.append(line)
                continue

            # Unrecognised: it continues whatever came last. Before the date
            # line that is the title, which is how a wrapped heading is
            # recovered; after a field it belongs to that field.
            if self.last_field is not None:
                self.fields[self.last_field].append(line.strip())
            elif self.when is None:
                self.title_parts.append(line.strip())

    def _take_field(self, line: str) -> bool:
        for key, pattern in _FIELDS.items():
            match = pattern.match(line.strip())
            if match is None:
                continue
            self.fields.setdefault(key, []).append(match.group("value").strip())
            self.last_field = key
            return True
        return False

    def field(self, key: str) -> str | None:
        parts = [part for part in self.fields.get(key, []) if part]
        return " ".join(parts) or None if parts else None

    def build(self) -> ImportedCall:
        when = self.when
        status = self.status
        day: date | None = None
        if when is not None and when.group("date"):
            try:
                # Naive: the corpus states local wall-clock times, and a zone
                # attached here would be one the source never gave.
                day = datetime.strptime(when.group("date"), "%d %b %Y").date()  # noqa: DTZ007
            except ValueError:
                day = None

        aht = when.group("aht") if when is not None else None
        handle_seconds = parse_handle_time(aht) if aht else None
        start = when.group("start") if when is not None else None
        end = (when.group("end") if when is not None else None) or _end_from(
            start, handle_seconds, day
        )
        queue = when.group("queue") if when is not None else None

        return ImportedCall(
            number=self.number,
            title=" ".join(part for part in self.title_parts if part).strip()
            or f"Call {self.number}",
            call_date=day,
            start=start,
            end=end,
            handle_seconds=handle_seconds,
            queue=queue.strip() if queue else None,
            caller=status.group("caller") if status else None,
            tier=status.group("tier").upper() if status else None,
            score=int(status.group("score")) if status else None,
            resolution=" ".join(status.group("resolution").split()) if status else None,
            start_mood=" ".join(status.group("start_mood").split()) if status else None,
            end_mood=" ".join(status.group("end_mood").split()) if status else None,
            agent=status.group("agent").strip() if status else None,
            context=self.field("context"),
            topics=self.field("topics"),
            broker=_normalise_broker(self.field("broker")),
            repeat=self.field("repeat"),
            transcript="\n".join(self.transcript).strip(),
            panel="\n".join(self.panel).strip(),
        )


def extract_calls(text: str) -> list[ImportedCall]:
    """Every call in the document, in the order it appears.

    Raises:
        ValidationError: if the document has no call headings at all, if two
            calls claim one number, or if any heading failed to yield a call.
    """
    lines = _clean(text)
    starts = [(index, match) for index, line in enumerate(lines) if (match := _HEADING.match(line))]
    if not starts:
        raise ValidationError(
            "No call headings were found in that document.",
            detail=(
                "Every call must begin with a line like "
                "'Call #1 — Why Am I Paying a Copay?'. Is this a call-corpus PDF?"
            ),
        )

    calls: list[ImportedCall] = []
    for position, (index, match) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        block = _Block(int(match.group("number")), match.group("title"))
        block.read(lines[index + 1 : end])
        calls.append(block.build())

    _reject_duplicates(calls)

    # The count is the one thing this parser will not be lenient about. A
    # heading that produced no transcript is a call that would vanish from the
    # conversion while the summary still reported success.
    empty = sorted(call.number for call in calls if not call.transcript)
    if empty:
        raise ValidationError(
            f"{len(empty)} of {len(starts)} calls have no transcript.",
            detail=f"Calls {empty} were found but no speaker turns were read from them.",
        )
    return calls


def _reject_duplicates(calls: list[ImportedCall]) -> None:
    """Two calls sharing a number would overwrite one another silently."""
    # Counted rather than the set-and-`add` trick this used to use: that relied
    # on `set.add` returning None to keep the `or` falsy, which reads as a bug
    # even when it is not, and mypy flags it as one.
    seen = Counter(call.number for call in calls)
    clashes = sorted(number for number, count in seen.items() if count > 1)
    if clashes:
        raise ValidationError(
            "The document numbers two calls the same.",
            detail=f"Call numbers appearing more than once: {clashes}.",
        )


def format_transcript(transcript: str) -> str:
    """One turn per paragraph, each on a single line.

    Two problems with writing the PDF's lines out as they came:

    * **The PDF hard-wraps mid-sentence.** A turn arrives as "Can I take your
      name and" / "group number?", so the file reads as though the agent said
      half a sentence.
    * **Markdown joins consecutive lines.** A single newline is not a line
      break, so every turn in the call renders as one run-on paragraph with the
      agent and the member indistinguishable — which is what a reader opening
      one of these files in any markdown viewer actually sees.

    So each turn is joined onto one line and separated from the next by a blank
    line. The turn *text* is unchanged: :func:`domain.parsing.parse_transcript`
    already joins wrapped continuations with a single space, so this writes down
    what the pipeline was computing anyway — which is what keeps the stored
    quote offsets valid.
    """
    turns: list[list[str]] = []
    for raw in transcript.splitlines():
        line = raw.strip()
        if not line:
            continue
        if _TURN.match(line) or not turns:
            turns.append([line])
        else:
            turns[-1].append(line)
    return "\n\n".join(" ".join(parts) for parts in turns)


def render(call: ImportedCall) -> str:
    """One call as the markdown the corpus parser reads.

    Only fields the document actually stated are written. An absent line is
    better than an invented one: the markdown parser treats a missing field as
    "not stated", and a placeholder would be indistinguishable from data.
    """
    lines = [f"# Call #{call.number} — {call.title}", ""]

    def bullet(label: str, value: object | None) -> None:
        if value not in (None, ""):
            lines.append(f"- **{label}:** {value}")

    bullet("Agent", call.agent)
    bullet("Caller", call.caller)
    bullet("Tier", call.tier)
    bullet("Score", f"{call.score}/100" if call.score is not None else None)
    arc = (
        f"{call.start_mood} → {call.end_mood}"
        if call.start_mood and call.end_mood
        else call.start_mood
    )
    bullet("Sentiment Arc", arc)
    bullet("Resolution", call.resolution)
    bullet("Date", call.call_date.isoformat() if call.call_date else None)
    bullet("Start", call.start)
    bullet("End", call.end)
    bullet("AHT", call.handle_time)
    # Both forms: the seconds are what the corpus states, and the rounded
    # minutes keep the field readable beside the older files.
    bullet(
        "Duration",
        f"~{round(call.handle_seconds / 60)} min" if call.handle_seconds else None,
    )
    bullet("Queue", call.queue)
    # The bullet the corpus parser already reads for broker names: it takes the
    # name from before the colon and leaves the rest as the author's account.
    bullet("Broker Signal", call.broker)
    bullet("Repeat Contact", call.repeat)
    bullet("Topics", call.topics)

    if call.context:
        lines += ["", f"**Member context:** {call.context}"]
    lines += ["", TRANSCRIPT_HEADING, "", format_transcript(call.transcript), ""]
    if call.panel:
        lines += [f"{PANEL_HEADING} — NanoVox 5-Layer Output", "", call.panel, ""]
    return "\n".join(lines)


class PdfCorpusDocumentReader(CorpusDocumentReader):
    """Reads corpus PDFs. Stateless, so one instance serves every request."""

    def extract(self, data: bytes) -> tuple[ImportedCall, ...]:
        return tuple(extract_calls(read_pdf(data)))

    def render(self, call: ImportedCall) -> str:
        return render(call)
