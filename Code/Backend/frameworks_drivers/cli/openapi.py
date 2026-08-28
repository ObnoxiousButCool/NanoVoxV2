"""Write the OpenAPI document to a file.

The frontend's TypeScript types are generated from this, so a contract change
that the frontend has not accounted for becomes a build failure rather than a
runtime surprise (plan §7.5).

Run from ``Code/Backend``::

    python -m frameworks_drivers.cli.openapi ../Frontend/openapi.json

The application is never started, so no database or model provider is needed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from domain.errors import NanoVoxError
from frameworks_drivers.main import create_app
from infrastructure.config.settings import get_settings

DEFAULT_OUTPUT = Path("..") / "Frontend" / "openapi.json"

EXIT_OK = 0
EXIT_FAILED = 1


def _out(line: str) -> None:
    sys.stdout.write(f"{line}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the OpenAPI document to a file.")
    parser.add_argument(
        "output", nargs="?", type=Path, default=DEFAULT_OUTPUT, help="Destination file."
    )
    arguments = parser.parse_args(argv)

    try:
        document = create_app(get_settings()).openapi()
    except NanoVoxError as exc:
        _out(f"FAILED: {exc.message}")
        return EXIT_FAILED

    destination = Path(arguments.output).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Sorted keys and a trailing newline so regenerating an unchanged API
    # produces a byte-identical file, which is what lets CI diff it.
    destination.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _out(f"Wrote {len(document.get('paths', {}))} paths to {destination}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
