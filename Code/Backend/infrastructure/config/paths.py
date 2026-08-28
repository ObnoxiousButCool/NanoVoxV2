"""Well-known filesystem locations, derived from this file's own position.

Deriving the roots from ``__file__`` keeps absolute paths out of the source. Every
path below is only a *default*: each is overridable through configuration, so a
deployment that does not look like this checkout still works.
"""

from __future__ import annotations

from pathlib import Path

# .../NanoVox-V2/Code/Backend/infrastructure/config/paths.py
#     parents[0] = config      parents[1] = infrastructure
#     parents[2] = Backend     parents[3] = Code            parents[4] = NanoVox-V2
_THIS_FILE = Path(__file__).resolve()

BACKEND_ROOT: Path = _THIS_FILE.parents[2]
PROJECT_ROOT: Path = _THIS_FILE.parents[4]

DEFAULT_LOG_DIR: Path = PROJECT_ROOT / "Logs"
DEFAULT_DATA_DIR: Path = PROJECT_ROOT / "Data"
DEFAULT_DATABASE_FILE: Path = DEFAULT_DATA_DIR / "nanovox.db"
DEFAULT_CORPUS_DIR: Path = PROJECT_ROOT / "Samples"
DEFAULT_CONFIG_DIR: Path = BACKEND_ROOT / "config"
DEFAULT_TAXONOMY_PATH: Path = DEFAULT_CONFIG_DIR / "taxonomy.yaml"
DEFAULT_RUBRIC_PATH: Path = DEFAULT_CONFIG_DIR / "rubric.yaml"


def default_database_url() -> str:
    """SQLite URL for the default on-disk database, as a POSIX-style path.

    SQLAlchemy URLs use forward slashes on every platform, including Windows.
    """
    return f"sqlite+aiosqlite:///{DEFAULT_DATABASE_FILE.as_posix()}"
