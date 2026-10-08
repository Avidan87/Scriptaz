# Scriptaz data-pack release process

Scriptaz keeps source code in Git and distributes its reusable Scripture library as a versioned release asset. This avoids a very large clone while preserving the full local experience: translations, passages, semantic indexes, preset journeys, and offline search data.

## Privacy boundary

The release pack must contain shared library data only. It must never contain a person's name, settings, personal context, custom themes, pins, notes, delivery history, queue state, or AI/cache history. `scripts/build_data_pack.py` starts from a copy of the maintainer database and removes those tables or resets their delivery state before producing the pack.

## Before creating a release

1. Confirm that every Bible translation and source asset is licensed for the intended public redistribution. KJV, ESV, NKJV, and NLT have different rights; do not publish a pack containing a translation until its permission and required attribution are documented.
2. Use a database populated with only approved shared content.
3. Build the asset without touching the source database:

   ```bash
   python scripts/build_data_pack.py /path/to/scriptaz.sqlite dist/scriptaz-data-v1.sqlite.gz
   ```

4. Upload both `scriptaz-data-v1.sqlite.gz` and its adjacent `.sha256` file to a GitHub Release.
5. Put the release URL and checksum in the distributed app configuration as `SCRIPTAZ_DATA_PACK_URL` and `SCRIPTAZ_DATA_PACK_SHA256`.

## First launch behaviour

If there is no local database and a release URL is configured, Scriptaz downloads the asset to a temporary file, verifies its SHA-256, validates the SQLite header, and atomically moves it into the application-data directory. A partial or invalid download cannot replace an existing library. If the URL is absent or unavailable, the app remains open and can show a clear setup message rather than crashing.

## Versioning

Use a distinct release tag for each data-pack schema/content version, for example `data-v1`. Keep the app compatible with at least the current pack and document any minimum required app version in the release notes.
