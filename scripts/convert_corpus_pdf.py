"""Convert a call-corpus PDF into one markdown file per call.

The same conversion the Corpus import screen performs, as a command. It is a
thin front end over :mod:`infrastructure.corpus.pdf_document` and deliberately
carries no grammar of its own: this script used to hold its own copy, and a
corpus whose header shape had changed then parsed differently depending on
which route you came in by. One grammar, two front doors.

    python scripts/convert_corpus_pdf.py Documents/corpus.pdf Samples
    python scripts/convert_corpus_pdf.py Documents/corpus.pdf Samples --dry-run

Prefer the screen for anything an operator does. This exists for a scripted
rebuild and for looking at a document that will not import, where ``--dry-run``
prints the tally without writing anything.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "Code" / "Backend"
sys.path.insert(0, str(BACKEND))

from domain.errors import NanoVoxError  # noqa: E402
from infrastructure.corpus.pdf_document import (  # noqa: E402
    extract_calls,
    read_pdf,
    render,
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

    try:
        calls = extract_calls(read_pdf(args.pdf.read_bytes()))
    except NanoVoxError as exc:
        # Extraction is all-or-nothing, and the detail names the calls it could
        # not read — which is the only useful thing to print here.
        raise SystemExit(f"{exc.message}\n{exc.detail or ''}".rstrip()) from exc

    numbers = [call.number for call in calls]
    print(f"{len(calls)} calls: #{min(numbers)}-#{max(numbers)}")

    stated = [call.handle_seconds for call in calls if call.handle_seconds]
    if stated:
        total = sum(stated)
        print(f"handle time: {total / 3600:.1f} h total, {total / len(stated) / 60:.1f} min average")

    dates = [call.call_date for call in calls if call.call_date]
    if dates:
        print(f"dates: {min(dates)} to {max(dates)}")

    print(f"callers: {dict(Counter(call.caller for call in calls))}")
    print(f"tiers: {dict(Counter(call.tier for call in calls))}")
    brokered = [call.number for call in calls if call.broker]
    repeats = [call.number for call in calls if call.repeat]
    print(f"broker signals: {len(brokered)} calls")
    print(f"repeat contacts: {len(repeats)} calls")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    for call in calls:
        (args.out / call.filename).write_text(render(call), encoding="utf-8")
    print(f"\nwrote {len(calls)} files to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
