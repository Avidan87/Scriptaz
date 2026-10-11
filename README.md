# Scriptaz ✨

> A quiet, intelligent Scripture companion for the rhythm of your working day.

Scriptaz is a native desktop app that lives in your menu bar or system tray, bringing Scripture into the spaces between meetings, tasks, and ordinary moments—without becoming another noisy productivity app.

> **Platform availability:** Scriptaz is currently available for **macOS**. A Windows version is actively in development and will be released in a future update.

## The app

Scriptaz is a native **macOS desktop application**, not just a code sample. It runs as a quiet companion in the menu bar, with its Scripture library, notes, settings, and personal context stored locally on your device.

This repository contains the public source and setup guide for developers who want to explore, run, or extend Scriptaz. Windows support is in progress.

## What it offers

- 📖 **Four translations** — KJV, NKJV, ESV, and NLT, with quick comparison for any passage.
- 🌿 **Intentional themes** — Peace, Wisdom, Faith, Grace, and Provision, with guided teaching journeys rather than random verses.
- ⏰ **Gentle rhythm** — scheduled Scripture cards at the pace you choose, plus a quiet background mode.
- 📌 **Your verses** — pin passages, add notes, and keep an archive locally on your device.
- 🧠 **Semantic discovery** — local embeddings make it possible to find Scripture connected to a theme or personal context.
- 🔒 **Local-first by design** — your settings, pins, notes, history, and personal context remain on your machine.

## How it works

```text
Scripture data pack ──► local SQLite database ──► desktop app
                                                ├─ translations & comparison
                                                ├─ teaching journeys
                                                ├─ pins, notes & archive
                                                └─ semantic search

Optional AI provider ──► reflection / curation features
```

The core reading experience works locally. AI-powered curation is optional and requires your own provider credentials.

## Quick start (macOS)

1. Clone this repository.
2. Create and activate a Python virtual environment.
3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Follow the data-pack setup instructions below.
5. Launch the app:
   ```bash
   python main.py
   ```

## Data pack setup

The Scripture corpus and embeddings are distributed separately so the repository stays lightweight.

1. Download the latest `scriptaz-data` release from the repository's Releases page.
2. Extract it into the project directory, preserving the included folders.
3. Start Scriptaz normally.

The app expects the bundled SQLite database and semantic-search assets to be available locally.

## Optional AI features

To enable AI-assisted reflection or curation, configure your preferred model provider in a local `.env` file. A lightweight model is sufficient for most tasks; Amazon Bedrock is also a strong option for deployment-minded setups.

Never commit provider keys or personal local data.

## Development notes

- Scriptaz is designed as a local-first desktop experience.
- The public repository is intended to be runnable, inspectable, and extendable.
- macOS is the currently supported platform; Windows packaging is planned.

## License

See [LICENSE](LICENSE).
