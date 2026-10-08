"""Install and validate the optional shared Scriptaz data pack.

The data pack is a pre-built SQLite library containing Scripture content and
semantic indexes.  It is deliberately separate from Git history: downloading
large binary databases through a release asset keeps source clones small and
makes pack updates independently versionable.

No request is made unless a release URL is explicitly configured.
"""

from __future__ import annotations

from dataclasses import dataclass
import gzip
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
from typing import Optional
from urllib.request import Request, urlopen


SQLITE_HEADER = b"SQLite format 3\x00"


@dataclass(frozen=True)
class DataPackResult:
    """Outcome of a data-pack availability check or install attempt."""

    available: bool
    downloaded: bool
    message: str


def _is_sqlite_database(path: Path) -> bool:
    try:
        if not path.is_file() or path.stat().st_size <= len(SQLITE_HEADER):
            return False
        with path.open("rb") as file_handle:
            return file_handle.read(len(SQLITE_HEADER)) == SQLITE_HEADER
    except OSError:
        return False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_data_pack(
    db_path: Path,
    release_url: Optional[str],
    expected_sha256: Optional[str] = None,
    timeout_seconds: int = 45,
) -> DataPackResult:
    """Ensure a valid local data pack exists, downloading it atomically if needed.

    ``expected_sha256`` is the checksum of the release asset, before any gzip
    extraction.  A bad or interrupted download never replaces a working local
    database.  Errors are returned to the caller rather than preventing the
    app from opening; the UI can still explain how to install the data pack.
    """
    if _is_sqlite_database(db_path):
        return DataPackResult(True, False, "A local Scriptaz data pack is ready.")

    if not release_url:
        return DataPackResult(
            False,
            False,
            "No Scriptaz data-pack release URL is configured. Set SCRIPTAZ_DATA_PACK_URL before distribution.",
        )

    db_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = ".sqlite.gz" if release_url.lower().split("?")[0].endswith(".gz") else ".sqlite"
    archive_path: Optional[Path] = None
    unpacked_path: Optional[Path] = None

    try:
        with tempfile.NamedTemporaryFile(dir=db_path.parent, prefix=".scriptaz-pack-", suffix=suffix, delete=False) as tmp:
            archive_path = Path(tmp.name)
            request = Request(release_url, headers={"User-Agent": "Scriptaz data-pack installer"})
            with urlopen(request, timeout=timeout_seconds) as response:
                shutil.copyfileobj(response, tmp)

        if expected_sha256 and _sha256(archive_path).lower() != expected_sha256.lower():
            return DataPackResult(False, False, "The downloaded data pack failed checksum verification.")

        if suffix.endswith(".gz"):
            with tempfile.NamedTemporaryFile(dir=db_path.parent, prefix=".scriptaz-pack-unpacked-", suffix=".sqlite", delete=False) as tmp:
                unpacked_path = Path(tmp.name)
                with gzip.open(archive_path, "rb") as packed:
                    shutil.copyfileobj(packed, tmp)
        else:
            unpacked_path = archive_path

        if not _is_sqlite_database(unpacked_path):
            return DataPackResult(False, False, "The downloaded file is not a valid SQLite data pack.")

        os.replace(unpacked_path, db_path)
        unpacked_path = None
        return DataPackResult(True, True, "The Scriptaz data pack was installed successfully.")
    except Exception as error:  # First-run access should fail gracefully, not crash the app.
        return DataPackResult(False, False, f"Could not download the Scriptaz data pack: {error}")
    finally:
        for temporary_path in (archive_path, unpacked_path):
            if temporary_path:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass
