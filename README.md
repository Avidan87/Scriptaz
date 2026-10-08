# Scriptaz ✨

> A quiet, intelligent Scripture companion for the rhythm of your working day.

Scriptaz is a native desktop app that lives in your menu bar or system tray, bringing Scripture into the spaces between meetings, tasks, and ordinary moments—without becoming another noisy productivity app.

## What it offers

- 📖 **Four translations** — KJV, NKJV, ESV, and NLT, with quick comparison for any passage.
- 🌿 **Intentional themes** — Peace, Wisdom, Faith, Grace, and Provision, with guided teaching journeys rather than random verses.
- ⏰ **Gentle rhythm** — scheduled Scripture cards at the pace you choose, plus a quiet background mode.
- 📌 **Your verses** — pin passages, add notes, and keep an archive locally on your device.
- 🧠 **Semantic discovery** — local embeddings make it possible to find Scripture connected to a theme or personal context.
- 🔒 **Local-first by design** — your settings, pins, notes, history, and personal context remain on your machine.

## How it works

```text
Scripture data pack → local SQLite library → theme / journey selection → desktop Scripture card
                                      ↘ optional Bedrock AI → personalised custom themes
```

The Scripture library and semantic index are delivered as a versioned release asset rather than committed to Git. On first launch, Scriptaz downloads the data pack, verifies its checksum, and stores it in the application-data folder. The app then reads Scripture locally.

## Quick start

```bash
git clone https://github.com/Avidan87/Scriptaz.git
cd Scriptaz
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py --welcome
```

On Windows, activate the environment with `.venv\\Scripts\\activate`.

## Optional AI curation

Scriptaz works without an API key. AI is optional and is used only for features such as personalised custom-theme curation and deeper semantic discovery.

The reference provider is Amazon Bedrock. To enable it, copy `.env.example` to `.env`, then configure AWS using your preferred secure method. The defaults are cost-conscious:

- `us.deepseek.r1-v1:0` for richer curation
- `amazon.nova-lite-v1:0` as a fast fallback
- `amazon.titan-embed-text-v2:0` for semantic embeddings

Never commit `.env` files, AWS keys, or personal data.

## Architecture

```text
┌─────────────┐      ┌───────────────────┐      ┌──────────────────┐
│ Native UI   │ ───▶ │ Local SQLite      │ ───▶ │ Scripture cards  │
│ PySide6     │ ◀─── │ verses + indexes  │ ◀─── │ tray scheduler   │
└─────────────┘      └─────────┬─────────┘      └──────────────────┘
                               │
                               │ optional
                               ▼
                      ┌───────────────────┐
                      │ Amazon Bedrock    │
                      │ theme curation    │
                      └───────────────────┘
```

## Project structure

```text
core/       configuration, local database, data-pack installation, models
engine/     API, semantic search, and optional Bedrock orchestration
services/   scheduling, auto-start, and platform integration
ui/         native PySide6 desktop interface
scripts/    data preparation and maintainer utilities
docs/       data-pack and release documentation
```

## Data-pack releases

The full Scriptaz library is available through the project’s [GitHub Releases](https://github.com/Avidan87/Scriptaz/releases). It is checksum-verified before installation so an interrupted or corrupt download never replaces a working local library.

Maintainers can find the packaging process in [the data-pack guide](docs/DATA_PACK.md).
