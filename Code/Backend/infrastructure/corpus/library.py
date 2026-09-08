"""Imported corpora on disk, one directory per named version.

Kept beside the shipped corpus rather than in it. ``Samples/`` holds the corpus
the stored analyses were made from, and an import that overwrote it would leave
a hundred rows in the database describing transcripts that no longer exist —
still shown on the dashboard, no longer checkable against anything. So an
import lands in ``Samples/imported/<name>/`` and nothing points at it until
somebody says so.

A name is slugged before it reaches the filesystem. The name comes from an
uploaded filename, which is attacker-controlled in principle and
``../``-controlled in practice.
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from application.ports.corpus_document import CorpusLibrary, SavedCorpus
from domain.errors import ValidationError

#: Where imports live, relative to the corpus directory.
IMPORT_SUBDIRECTORY = "imported"

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
_MAX_NAME = 60


def slugify(name: str) -> str:
    """A filesystem-safe directory name.

    Rejects rather than silently substitutes when nothing usable survives: an
    import saved under a name the operator did not choose is one they will not
    find again.
    """
    stem = Path(name).stem.lower()
    slug = _SLUG_STRIP.sub("-", stem).strip("-")[:_MAX_NAME]
    if not slug:
        raise ValidationError(
            "That filename cannot be used as a corpus name.",
            detail=f"{name!r} contains no letters or digits to name a directory with.",
        )
    return slug


class FileSystemCorpusLibrary(CorpusLibrary):
    """Stores imported corpora under ``<corpus_path>/imported/<name>/``."""

    def __init__(self, corpus_path: Path, glob: str) -> None:
        self._root = corpus_path / IMPORT_SUBDIRECTORY
        self._glob = glob

    @property
    def root(self) -> Path:
        return self._root

    def directory_for(self, name: str) -> Path:
        return self._root / slugify(name)

    def save(self, name: str, files: dict[str, str]) -> SavedCorpus:
        if not files:
            raise ValidationError("There is nothing to save: the document yielded no calls.")

        directory = self.directory_for(name)
        # Replaced wholesale rather than merged. A re-import of a document with
        # fewer calls must not leave the surplus of the previous one behind,
        # which would then be analysed as though it came from this document.
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)

        for filename, content in sorted(files.items()):
            (directory / filename).write_text(content, encoding="utf-8")

        return SavedCorpus(name=directory.name, directory=directory, files=len(files))

    def versions(self) -> tuple[SavedCorpus, ...]:
        if not self._root.is_dir():
            return ()
        found = [
            SavedCorpus(
                name=child.name,
                directory=child,
                files=len(list(child.glob(self._glob))),
            )
            for child in self._root.iterdir()
            if child.is_dir()
        ]
        return tuple(sorted(found, key=lambda saved: _modified(saved.directory), reverse=True))


def _modified(directory: Path) -> datetime:
    """When this import was written, for ordering newest first.

    Both paths are timezone-aware, and have to be: the two are compared against
    each other by the sort, and mixing a naive datetime with an aware one raises
    rather than sorting wrongly.
    """
    try:
        return datetime.fromtimestamp(directory.stat().st_mtime, tz=timezone.utc)
    except OSError:  # pragma: no cover - a directory removed under us
        # Sorts last, which is where a directory we cannot stat belongs.
        return datetime.min.replace(tzinfo=timezone.utc)
