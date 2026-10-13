"""Central data-directory resolution for Lumina.

User data (SQLite DB, Chroma vectors, uploaded documents) lives in the OS
application-data directory instead of inside the source tree, so reinstalls
or upgrades never touch it:

    Windows : %APPDATA%\\Lumina
    macOS   : ~/Library/Application Support/Lumina
    Linux   : ~/.local/share/Lumina

Override for development/tests with the LUMINA_DATA_DIR environment variable.
On first run, data previously stored inside backend/ is migrated across.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

APP_NAME = "Lumina"

BACKEND_DIR = Path(__file__).resolve().parent


def _default_data_root() -> Path:
    override = os.environ.get("LUMINA_DATA_DIR")
    if override:
        return Path(override)

    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / APP_NAME

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME

    # Linux / other Unix
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / APP_NAME


DATA_ROOT = _default_data_root()
DB_DIR = DATA_ROOT / "data"
DB_PATH = DB_DIR / "lumina.db"
CHROMA_ROOT = DATA_ROOT / "chroma_db"
DOCUMENTS_ROOT = DATA_ROOT / "documents"


def _migrate_legacy() -> None:
    """Copy pre-existing data out of the backend folder on first run."""
    legacy_map = [
        (BACKEND_DIR / "data", DB_DIR),
        (BACKEND_DIR / "chroma_db", CHROMA_ROOT),
        (BACKEND_DIR / "documents", DOCUMENTS_ROOT),
    ]
    for old, new in legacy_map:
        if old.resolve() == new.resolve():
            continue
        if old.is_dir() and not new.exists():
            new.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(old, new)
            print(f"Lumina: migrated {old} -> {new}")


_migrate_legacy()

DB_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_ROOT.mkdir(parents=True, exist_ok=True)
DOCUMENTS_ROOT.mkdir(parents=True, exist_ok=True)

# String forms for libraries that don't accept pathlib paths
CHROMA_ROOT_STR = str(CHROMA_ROOT)
DOCUMENTS_ROOT_STR = str(DOCUMENTS_ROOT)
