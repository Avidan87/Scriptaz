# 📖 Scriptaz — Master Product & Technical Architecture Specification

> **Application Name**: Scriptaz (`Scriptaz.app` / `Scriptaz.exe`)  
> **Tagline**: The Intelligent, Context-Sound Scripture Companion for Your Workday  
> **Platform**: Native macOS & Windows Desktop  
> **Core Architecture**: Offline-First Local Data + Pre-computed Vector Graph + Provider-Agnostic LLM Streaming Engine (DeepSeek / Local Ollama / AWS Bedrock / OpenAI)

---

## 1. Executive Summary & Vision

**Scriptaz** is a non-intrusive, beautiful desktop companion designed for professionals, developers, and students spending 8–12 hours a day on their laptops. 

Instead of overwhelming users with random scripture notifications or disconnected life-coaching tips, **Scriptaz** delivers:
1. **Periodic, Paced Scripture Drops**: Paced at user-customized intervals (30m to 2h) with strict daily limits (1 to 10 verses).
2. **Context-Sound Revelation**: Every verse is anchored in its historical narrative and covenant setting—never isolated or proof-texted.
3. **On-Demand Deep Insights**: A live token-streamed breakdown providing historical context, original Hebrew/Greek root word meanings, and Christ-centered covenantal fulfillment.
4. **Seamless Personalization**: The user's personal workday struggle is woven directly into the redemptive truth of the Gospel without moralizing or preachy checklists.
5. **No Auto-Dismiss**: Cards remain quietly on screen until explicitly closed by the user.

---

## 2. Core User Experience & Workday Lifecycle

```
┌────────────────────────────────────────────────────────────────────────┐
│                        1. CONTROL PANEL (Setup)                        │
├────────────────────────────────────────────────────────────────────────┤
│ • Interval Timer: 30 minutes to 2 hours                                │
│ • Bible Version: KJV, ESV, NLT, AMP, etc.                              │
│ • Theme: Sin & Grace, New Birth, Authority, Faith, Peace, etc.         │
│ • Daily Limit: Number of unique verses dished per day (1 to 10)        │
│ • Personal Context: "Why did you choose this theme?" (Optional text)   │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼ (Periodic Timer Triggers on Active Laptop)
┌────────────────────────────────────────────────────────────────────────┐
│                      2. DESKTOP POPUP CARD                             │
├────────────────────────────────────────────────────────────────────────┤
│  AUTHORITY                                                [ ⚲ Pin ]    │
│                                                                        │
│  "Behold, I give unto you power to tread on serpents and               │
│   scorpions, and over all the power of the enemy: and                  │
│   nothing shall by any means hurt you."                                │
│                                            — Luke 10:19 (KJV)          │
│                                                                        │
│  [ ✦ Deep Insight ]                                         [ × Close ]│
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
         ┌─────────────────────────┴─────────────────────────┐
         ▼                                                   ▼
┌───────────────────────────────────┐       ┌───────────────────────────────────┐
│       IF USER CLICKS [ ⚲ PIN ]    │       │  IF USER CLICKS [ ✦ DEEP INSIGHT ]│
├───────────────────────────────────┤       ├───────────────────────────────────┤
│ • Locks verse into rotation.      │       │ • Card smoothly expands down.     │
│ • Re-dishes this verse across     │       │ • Checks SQLite Cache (0ms if in) │
│   following days according to     │       │ • If fresh: Streams tokens live   │
│   timer & daily limit.            │       │   (200ms) with zero raw markdown  │
│ • Stays active until unpinned.    │       │ • 3-part biblical exposition.     │
└───────────────────────────────────┘       └───────────────────────────────────┘
```

---

## 3. Detailed Feature Specifications

### A. The Control Panel (Settings & Preferences)
* **Popup Frequency**: Configurable slider from **30 minutes to 2 hours** (e.g. 30m, 45m, 1h, 1.5h, 2h).
* **Bible Version**: Dropdown selector (KJV, ESV, NLT, AMP, NASB, etc.).
* **Theme Selection**: Short, punchy theme tags:
  * `Sin & Grace`
  * `New Birth`
  * `Authority`
  * `Faith`
  * `Peace`
  * `Healing`
  * `Wisdom`
  * `Provision & Diligence`
  * `Salvation`
  * `Love & Joy`
* **Personal Context Input (*Why this theme?*)**:
  * Open multiline text area where the user can share their current situation (*e.g., "Battling guilt over a work mistake and feeling condemned"* or *"Struggling with sexual temptation and feeling defeated"*).
  * Informs the vector search for scripture matching and tailors the Christ-centered revelation.
* **Daily Scripture Limit**: Selector for **1 to 10 verses per active day**.
* **Launch on Startup**: Optional checkbox to start silently in the background when the laptop boots.

### B. Adaptive OS Design (macOS & Windows)
* **macOS**:
  * System Font: **SF Pro**.
  * Window Chrome: Traffic lights (🔴🟡🟢) top-left, floating frameless cards with macOS rounded corners and native hardware drop shadow.
  * System Menu Bar: Sits cleanly in the top menu bar next to the clock/battery.
* **Windows**:
  * System Font: **Segoe UI**.
  * Window Chrome: Fluent Design standards, title bar controls top-right.
  * System Tray: Lives in the bottom-right taskbar tray.

### C. Active-Time Queue Management (Sequential Flow)
* **Active-Time Tracking**: Popups only trigger when the user is actively working on their laptop. Timers pause during system sleep.
* **Sequential Resume (No Lost Verses)**: If a user sets 8 verses/day and only works 5 hours (seeing 5 verses), the system automatically resumes at **Verse 6** the next morning.

### D. The Pin (⚲) Mechanism
* Clicking the **Pin** icon on any popup card locks that scripture into active rotation.
* The system continues serving the pinned scripture across subsequent days according to the user's timer interval and quota.
* Pinned scriptures are permanently preserved in the user's **"My Verses"** archive tab.

### E. Persistent Visibility (NO Auto-Dismiss)
* The popup card **never** uses an automatic countdown timer.
* It remains comfortably on screen until the user explicitly clicks `[ × Close ]`.

---

## 4. Deep Insight Exposition Framework & Prompt Design

### A. The 3-Part Expository Structure
The Deep Insight output is parsed into clean, custom-styled visual containers with **zero raw markdown artifacts** (no `#`, no `*`):

1. **`HISTORICAL CONTEXT`**: 2–3 sentences identifying the speaker, audience, historical narrative, and covenant setting.
2. **`ORIGINAL LANGUAGE KEY`**: Highlighting 1–2 key Hebrew/Greek root lemmas, transliterations, Strong's definitions, and the exact spiritual depth unlocked.
3. **`CHRIST-CENTERED REVELATION & CONNECTED SCRIPTURES`**:
   * Bridges the text to the finished work of Jesus Christ and New Covenant grace.
   * **Personal Context Infusion**: Dynamically weaves the user's struggle (e.g. habitual sin, anxiety, finances) directly into the victory of the Gospel without moralizing checklists.
   * Followed by 2 explicit, relevant cross-referenced scriptures.

---

### B. Production System Prompt Template

```text
You are a contextually grounded, reverent Christian Biblical Scholar and Expository Exposition Engine rooted in the finished work of Jesus Christ.

YOUR MISSION:
Deliver profound, linguistically sound, and Christ-centered illumination for a specific Scripture passage, speaking directly to the believer's spiritual reality and personal battle.

STRICT OPERATIONAL RULES:

1. THEOLOGICAL INTEGRITY:
   - Always honor the historical-grammatical context (speaker, audience, covenantal setting). Never pull a verse out of its surrounding narrative.
   - All Scripture (both Old and New Testaments) finds its fulfillment and redemptive substance in the Person and finished work of Jesus Christ.

2. WEAVING THE USER'S PERSONAL CONTEXT:
   - When the user provides a personal challenge, struggle, or context (e.g., battling habitual sin, sexual temptation, anxiety, financial stress, sickness, grief):
     * Do NOT create a separate "advice" or "tips" section.
     * Do NOT scold, judge, or preach legalistic moralism.
     * INSTEAD, seamlessly weave the power of the Gospel into the "CHRIST-CENTERED REVELATION" section. Explain how Christ's finished work, righteousness, and grace specifically break the power, fear, guilt, and dominion of that exact struggle.

3. ORIGINAL LANGUAGE PRECISION:
   - Highlight 1 to 2 key Hebrew (Old Testament) or Greek (New Testament) root words.
   - Include the transliteration, original Strong's definition, and the exact spiritual depth unlocked by that specific root word.

4. DYNAMIC SYNTHESIS DIRECTIVE (ZERO BOILERPLATE):
   - You must never use generic canned templates, repetitive cliches, or boilerplate language.
   - Dynamically analyze the precise intersection between the TARGET SCRIPTURE, its surrounding narrative, and the USER'S REAL-TIME STRUGGLE.
   - For CONNECTED SCRIPTURES: Dynamically select and explain cross-references that specifically illuminate the redemptive bridge between this text and the user's situation. 
   - Every single generated insight must feel unique, context-accurate, and specifically ministered for this text and context.

5. STRUCTURE & BREVITY:
   - Deliver your response strictly using the 3 specified headings.
   - Keep the entire output concise, punchy, and readable in under 60 seconds (approx. 200-280 words total).
```

---

### C. Dynamic User Prompt Payload

```text
Please provide deep contextual and Christ-centered illumination for this scripture:

[SCRIPTURE DETAILS]
Reference: {scripture_reference}
Bible Translation: {bible_version}
Verse Text: "{verse_text}"

[SURROUNDING CHAPTER CONTEXT]
{surrounding_chapter_summary}

[USER PROFILE & CONTEXT]
Active Theme: {active_theme}
User's Personal Context / Struggle: {user_personal_context_or_empty}

---
Format your response STRICTLY with these 3 markdown sections:

### 🏛️ CONTEXT & SETTING
(2-3 sentences explaining the historical narrative, speaker, audience, and immediate chapter context)

### 🔍 ORIGINAL WORD ILLUMINATION
(1-2 key Greek or Hebrew root words, transliteration, definition, and the depth they unlock)

### ✝️ CHRIST-CENTERED REVELATION & CONNECTED SCRIPTURES
(How this truth culminates in Christ's finished work, ministering grace, victory, and freedom directly into the user's focus/struggle. Follow with 2 connected cross-referenced scripture verses with brief 1-sentence explanations)
```

---

## 5. Technical & Cloud-Agnostic Architecture

The system is designed with a **Pluggable Provider Pattern**, making it completely decoupled from any single cloud vendor:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              1. LOCAL STORAGE (SQLite)                                 │
│                                                                                        │
│  • Bible Texts (KJV, ESV, etc.)           • Pre-computed Dense Vector Embeddings       │
│  • Strong's Lexicon (Greek/Hebrew)        • Deep Insight Local Cache Table             │
│  • User Preferences & Pinned Verses       • Active-Time Queue & Sequence State         │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                          2. DESKTOP CLIENT (PyQt6 / PySide6)                           │
│                                                                                        │
│  • macOS Menu Bar & Windows System Tray  • Frameless Floating Popup with Drop Shadow   │
│  • Smooth downward slide accordion       • Active-Time Screen Timer (30m - 2h)         │
│  • Local Vector Search Matcher (Cosine)  • Custom Typography Renderer (No raw MD)      │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ (User clicks [ ✦ Deep Insight ])
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                  3. PLUGGABLE LLM STREAMING ENGINE (Provider-Agnostic)                 │
│                                                                                        │
│   ┌────────────────────────────────────────────────────────────────────────────────┐   │
│   │ Check SQLite Cache: If hit -> Return instantly in 0ms ($0 cost)                │   │
│   └───────────────────────────────────────┬────────────────────────────────────────┘   │
│                                           │ (If miss -> Stream live)                   │
│                                           ▼                                            │
│   ┌────────────────────────────────────────────────────────────────────────────────┐   │
│   │ Pluggable Provider Interface (`ai_engine.py`):                                 │   │
│   │                                                                                │   │
│   │ • Option A: DeepSeek-V3 API (`deepseek-chat`) — Ultra-fast, <$0.40/yr cost     │   │
│   │ • Option B: 100% Local Offline (Ollama / DeepSeek-R1-Distill-7B / Qwen-2.5)    │   │
│   │ • Option C: Amazon Bedrock (Nova Lite / Claude 3.5 Haiku)                      │   │
│   │ • Option D: OpenAI / Anthropic direct API                                      │   │
│   └────────────────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. One-Time Embeddings & Local Caching Strategy

1. **Pre-computed Once Forever**:
   * Verses are embedded once and saved into `bible_vectors.sqlite`.
   * Embedding cost for the entire Bible is incurred once (~$0.03 via Titan V2, or $0.00 via local MiniLM).
   * Runtime matching is 100% local cosine similarity (<2ms).
2. **Deep Insight SQLite Cache**:
   * `cache_key = sha256(f"{verse_ref}_{theme}_{user_context}")`
   * Every streamed response is cached locally. Repeated views of the same scripture load in **0 milliseconds** with **$0 API cost**.

---

## 7. Packaging & Desktop Distribution

* **macOS Application**: Packaged via `py2app` or `PyInstaller` into a self-contained **`Scriptaz.app`** bundle with a custom gold scripture icon.
* **Installation**: Drag and drop into `/Applications`.
* **Runtime**: Runs silently in the macOS Menu Bar using under 35MB RAM.
* **Windows Application**: Packaged into a standalone **`Scriptaz.exe`** installer with Windows System Tray integration.

---

*Specification locked and saved for development.* 🚀
