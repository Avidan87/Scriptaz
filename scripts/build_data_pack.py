"""Build a distributable Scriptaz data pack without copying personal data.

This is a maintainer command. It never changes the source database: it copies
the library first, removes user-specific state from that copy, then writes a
compressed release asset and a SHA-256 checksum file.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile


PERSONAL_TABLES = (
    "user_settings",
    "pinned_verses",
    "custom_themes",
    "custom_theme_history",
    "active_queue",
    "theme_history",
    "insights_cache",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def table_names(connection: sqlite3.Connection) -> set[str]:
    return {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def create_data_pack(source: Path, destination: Path, force: bool = False) -> Path:
    if not source.is_file():
        raise FileNotFoundError(f"Source database does not exist: {source}")
    if destination.exists() and not force:
        raise FileExistsError(f"Destination already exists: {destination}. Use --force to replace it.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="scriptaz-pack-") as temporary_directory:
        sanitized = Path(temporary_directory) / "scriptaz-data.sqlite"
        with sqlite3.connect(source) as source_connection, sqlite3.connect(sanitized) as target_connection:
            source_connection.backup(target_connection)

        with sqlite3.connect(sanitized) as connection:
            existing = table_names(connection)
            for table in PERSONAL_TABLES:
                if table in existing:
                    connection.execute(f'DELETE FROM "{table}"')

            # Journey definitions are shared library content, but delivery state
            # belongs to an individual installation.
            if "theme_journey" in existing:
                # Custom journeys can encode someone else's personal prompt, so
                # they cannot travel in a public release asset.
                connection.execute("DELETE FROM theme_journey WHERE theme_key LIKE 'custom:%'")
                connection.execute("UPDATE theme_journey SET is_delivered = 0, delivered_at = NULL")
            connection.commit()
            connection.execute("VACUUM")

        with sanitized.open("rb") as source_file, gzip.open(destination, "wb", compresslevel=9) as output_file:
            shutil.copyfileobj(source_file, output_file)

    checksum_file = destination.with_suffix(destination.suffix + ".sha256")
    checksum_file.write_text(f"{sha256(destination)}  {destination.name}\n", encoding="utf-8")
    return checksum_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a privacy-safe Scriptaz SQLite release asset.")
    parser.add_argument("source", type=Path, help="Existing full Scriptaz SQLite library")
    parser.add_argument("destination", type=Path, help="Output path, normally scriptaz-data-v1.sqlite.gz")
    parser.add_argument("--force", action="store_true", help="Replace an existing output asset")
    args = parser.parse_args()

    checksum_file = create_data_pack(args.source, args.destination, force=args.force)
    print(f"Created {args.destination}")
    print(f"Wrote {checksum_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
