"""Convert a timestamped call-corpus PDF into one markdown file per call.

The corpus arrives as a single PDF. The application never reads it: this script
turns it into the same ``call_NNN.md`` files the pipeline already ingests, so the
PDF stays a source document rather than a runtime dependency. That matters
because a PDF text layer is lossy — the arrows and middle dots in this one come
back mangled under some encodings — and a conversion you can read, diff and
correct by hand is worth more than one that happens invisibly at ingest.

The v4 header is a five-line block:

    Call #1 — Why Am I Paying a Copay When I Have Dental Insurance?
    Thu 24 Sep 2026 · 10:41:15 – 10:46:36 · AHT 5m 21s
    MEMBER | POOR · 38/100 | UNRESOLVED | CONFUSED → FRUSTRATED | Agent: Brad
    Context: Alicia Ferrara, 34 · Delta Dental PPO via ChoiceBuilder · billed $48
    Topics: copay · preventive · dental · cost share · Delta Dental

which is rewritten as the bullet header the corpus parser reads, carrying the
new fields — date, start, end, handle time and caller type — as further bullets.

    python scripts/convert_corpus_pdf.py Documents/corpus.pdf Samples
    python scripts/convert_corpus_pdf.py Documents/corpus.pdf Samples --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

TRANSCRIPT_HEADING = "## Transcript"
PANEL_HEADING = "## AI Insights Panel"

# The panel heading in the PDF, which marks the end of the transcript.
_PANEL_MARKER = "AI INSIGHTS PANEL"

# The five header lines. Resolutions and sentiments are multiple words in this
# corpus ("PARTIALLY RESOLVED", "PARTIALLY SATISFIED"), so the upper-case runs
# have to allow spaces — matching \w+ alone silently skips those calls.
_UPPER = r"[A-Z][A-Z ]*[A-Z]|[A-Z]+"
_HEADER = re.compile(
    r"^Call #(?P<number>\d+)\s*[—–-]\s*(?P<title>.+)\n"
    r"\w{3}\s+(?P<date>\d{1,2} \w{3} \d{4})\s*·\s*(?P<start>[\d:]{8})\s*[–-]\s*(?P<end>[\d:]{8})"
    r"\s*·\s*AHT\s+(?P<aht>[^\n]+?)\s*\n"
    rf"(?P<caller>MEMBER|EMPLOYER|BROKER)\s*\|\s*(?P<tier>\w+)\s*·\s*(?P<score>\d+)/100\s*\|\s*"
    rf"(?P<resolution>{_UPPER})\s*\|\s*(?P<start_mood>{_UPPER})\s*→\s*(?P<end_mood>{_UPPER})\s*\|\s*"
    r"Agent:\s*(?P<agent>[^\n]+)\n"
    r"Context:\s*(?P<context>[^\n]+)\n"
    r"Topics:\s*(?P<topics>[^\n]+)$",
    re.MULTILINE,
)

_AHT = re.compile(r"^(?:(?P<minutes>\d+)\s*m)?\s*(?:(?P<seconds>\d+)\s*s)?$")


@dataclass(frozen=True)
class Call:
    """One call, lifted out of the PDF."""

    number: int
    title: str
    call_date: date
    start: str
    end: str
    handle_seconds: int
    caller: str
    tier: str
    score: int
    resolution: str
    start_mood: str
    end_mood: str
    agent: str
    context: str
    topics: str
    transcript: str
    panel: str

    @property
    def handle_time(self) -> str:
        minutes, seconds = divmod(self.handle_seconds, 60)
        return f"{minutes}m {seconds}s" if seconds else f"{minutes}m"


def read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise SystemExit(
            "pypdf is needed to read the corpus PDF.\n"
            "    pip install -r Code/Backend/requirements-dev.txt"
        ) from None

    reader = PdfReader(str(path))
    # Joined with newlines rather than page markers: a call block can straddle a
    # page break, and the header regex has to see its five lines as consecutive.
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def parse_handle_time(value: str) -> int:
    """``5m 21s`` as seconds. Raises rather than guessing, because handle time is
    the figure the whole time analysis rests on."""
    match = _AHT.match(value.strip())
    if match is None or not (match.group("minutes") or match.group("seconds")):
        raise ValueError(f"Unreadable handle time: {value!r}")
    return int(match.group("minutes") or 0) * 60 + int(match.group("seconds") or 0)


def parse_calls(text: str) -> list[Call]:
    """Every call in the document, in the order it appears."""
    matches = list(_HEADER.finditer(text))
    if not matches:
        raise SystemExit("No call headers found. Is this the timestamped corpus PDF?")

    calls: list[Call] = []
    for index, match in enumerate(matches):
        # The body runs to the next header, or to the end of the document.
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : body_end]

        panel_at = body.find(_PANEL_MARKER)
        transcript = (body[:panel_at] if panel_at >= 0 else body).strip()
        panel = body[panel_at + len(_PANEL_MARKER) :].strip() if panel_at >= 0 else ""

        calls.append(
            Call(
                number=int(match.group("number")),
                title=match.group("title").strip(),
                # Naive: the corpus states local wall-clock times, and a zone
                # attached here would be one the source never gave.
                call_date=datetime.strptime(  # noqa: DTZ007
                    match.group("date"), "%d %b %Y"
                ).date(),
                start=match.group("start"),
                end=match.group("end"),
                handle_seconds=parse_handle_time(match.group("aht")),
                caller=match.group("caller"),
                tier=match.group("tier").upper(),
                score=int(match.group("score")),
                resolution=" ".join(match.group("resolution").split()),
                start_mood=" ".join(match.group("start_mood").split()),
                end_mood=" ".join(match.group("end_mood").split()),
                agent=match.group("agent").strip(),
                context=match.group("context").strip(),
                topics=match.group("topics").strip(),
                transcript=transcript,
                panel=panel,
            )
        )
    return calls


def render(call: Call) -> str:
    """One call as the markdown the corpus parser reads."""
    return "\n".join(
        [
            f"# Call #{call.number} — {call.title}",
            "",
            f"- **Agent:** {call.agent}",
            f"- **Caller:** {call.caller}",
            f"- **Tier:** {call.tier}",
            f"- **Score:** {call.score}/100",
            f"- **Sentiment Arc:** {call.start_mood} → {call.end_mood}",
            f"- **Resolution:** {call.resolution}",
            f"- **Date:** {call.call_date.isoformat()}",
            f"- **Start:** {call.start}",
            f"- **End:** {call.end}",
            # Both forms: the seconds are what the corpus states, and the
            # rounded minutes keep the field readable beside the older files.
            f"- **AHT:** {call.handle_time}",
            f"- **Duration:** ~{round(call.handle_seconds / 60)} min",
            f"- **Topics:** {call.topics}",
            "",
            f"**Member context:** {call.context}",
            "",
            TRANSCRIPT_HEADING,
            "",
            call.transcript,
            "",
            f"{PANEL_HEADING} — NanoVox 5-Layer Output",
            "",
            call.panel,
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="the corpus PDF")
    parser.add_argument("out", type=Path, help="directory to write call_NNN.md into")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be written without writing it",
    )
    args = parser.parse_args(argv)

    if not args.pdf.is_file():
        raise SystemExit(f"No such file: {args.pdf}")

    calls = parse_calls(read_pdf(args.pdf))

    numbers = [call.number for call in calls]
    clashes = {n for n in numbers if numbers.count(n) > 1}
    if clashes:
        # Two calls sharing a number would overwrite one another silently, and
        # the pipeline would then reject the whole directory for duplicate
        # references — after the conversion had already thrown a call away.
        raise SystemExit(f"Call numbers appear more than once: {sorted(clashes)}")

    print(f"{len(calls)} calls: #{min(numbers)}–#{max(numbers)}")
    total = sum(call.handle_seconds for call in calls)
    print(f"handle time: {total / 3600:.1f} h total, {total / len(calls) / 60:.1f} min average")
    print(f"callers: {', '.join(sorted({call.caller for call in calls}))}")
    print(
        "dates: "
        f"{min(call.call_date for call in calls)} to {max(call.call_date for call in calls)}"
    )

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    for call in calls:
        path = args.out / f"call_{call.number:03d}.md"
        path.write_text(render(call), encoding="utf-8")
    print(f"\nwrote {len(calls)} files to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
