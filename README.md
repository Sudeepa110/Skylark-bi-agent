# 🚀 Skylark Monday.com Business Intelligence Agent

An executive-grade Conversational AI Business Intelligence Agent designed for founders and leadership teams. It dynamically queries, reconciles, and synthesizes real-time business data across two live **monday.com** boards:
1. **"Deals"** (`Deal funnel Data` — Sales Pipeline, Deal Stages, Probability & Commercial Velocity)
2. **"Work Orders"** (`Work_Order_Tracker Data` — Project Execution, Revenue Realization, Unbilled Backlog & Accounts Receivable)

Built for the **Skylark Drones Technical Assignment**, this agent provides full-funnel business visibility, resilient data normalization for messy real-world entries, transparent data quality auditing, proactive ambiguity detection, live **Text-to-Speech (TTS) Voice Synthesis & Voice Dictation**, and a modern **3-Tab Executive Workspace** with 1-click leadership briefings and live board data exploration.

---

## 🏛️ System Architecture

```
                                  +---------------------------------------+
                                  |      Founder / Executive User         |
                                  |    (Voice Dictation / Text Query)     |
                                  +---------------------------------------+
                                                      |
                                           [Natural Language / Voice]
                                                      v
+---------------------------------------------------------------------------------------------------+
|  EXECUTIVE 3-TAB WEB PLATFORM (HTML5 / Modern Dark Glassmorphic CSS / Vanilla JS)                 |
|  - TAB 1: 💬 BI Assistant (AI Chat with Gemini 3.6 Flash, Suggested Follow-ups, Live TTS Narration)|
|  - TAB 2: 📊 Executive Reports (1-Click C-Suite Weekly Briefing Generator & TTS Reader)           |
|  - TAB 3: 📁 Board Data Explorer (Searchable Live Data Grid for Deals & Work Orders Records)      |
|  - 4 Executive KPI Cards (Pipeline ₹340.29 Cr, Work Orders ₹21.16 Cr, Billed ₹10.74 Cr, Risks)    |
|  - Live Cache TTL Freshness Counter & Monday.com Integration Status Pill                          |
+---------------------------------------------------------------------------------------------------+
                                                      |
                                              [REST / JSON APIs]
                                                      v
+---------------------------------------------------------------------------------------------------+
|  FASTAPI APPLICATION CORE                                                                         |
|                                                                                                   |
|  +---------------------------+    +----------------------------+    +--------------------------+  |
|  | Conversational Agent      |    | Ambiguity Resolver         |    | Data Resilience Engine   |  |
|  | - Intent Classification   |--->| - Detects broad queries    |--->| - Date Normalization     |  |
|  | - Entity Extraction       |    | - Proactive options prompt |    | - Sector/Casing Mapping  |  |
|  | - Gemini 3.6 Flash Hybrid |    +----------------------------+    | - DQ Audit & Warnings    |  |
|  +---------------------------+                                      +--------------------------+  |
|               |                                                                   |               |
|               v                                                                   v               |
|  +---------------------------------------------------------------------------------------------+  |
|  | Deterministic Business Intelligence & Analytics Engine (Pandas & NumPy)                     |  |
|  | - Deterministic calculations (Zero arithmetic hallucinations)                               |  |
|  | - Cross-Board Key Harmonization (Client Code COMPANY089 <-> Customer Code WOCOMPANY_089)    |  |
|  | - Revenue Realization, Billed vs Unbilled Backlog, Cash Collections, AR Priority Analysis   |  |
|  +---------------------------------------------------------------------------------------------+  |
|                                               ^                                                   |
|                                               |                                                   |
|  +---------------------------------------------------------------------------------------------+  |
|  | Live Monday.com Client (GraphQL API v2)                                                     |  |
|  | - Dynamic schema discovery (state: all)      - Cursor-based pagination (346+ & 176+ items)  |  |
|  | - In-memory cache (120s TTL)                 - Exponential backoff & rate-limit resilience   |  |
|  | - Stale Cache Fallback on Network Loss       - Custom Exception & Error Handling Hierarchy   |  |
|  +---------------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------------+
                                                      |
                                          [Monday GraphQL API v2]
                                                      v
                                  +---------------------------------------+
                                  |       monday.com Live Cloud           |
                                  |   - Deal funnel Data (346 items)      |
                                  |   - Work_Order_Tracker Data (176 items|
                                  +---------------------------------------+
```

---

## ✨ Key Features

### 1. 💬 Founder-Level Conversational Interface with Gemini 3.6 Flash
- Natural language chat answering founder questions like:
  - *"How's our pipeline looking for energy sector this quarter?"*
  - *"What is our overall revenue and billing status?"*
  - *"Which work orders are currently marked as STUCK?"*
  - *"How are BD owners performing?"*
- **Grounding & Zero Hallucinations**: Exact numbers (Pipeline, Billed, Backlog, AR) are computed deterministically via Pandas and fed into Gemini 3.6 Flash for strategic executive framing.
- **Proactive Ambiguity Detection**: Flags underspecified questions and provides one-click selectable drill-down options.

### 2. 🎙️ Live Text-to-Speech (TTS) Voice Narration & Voice Dictation
- **Voice Mode (`🔊 Voice: ON/OFF`)**: Reads AI insights aloud in natural executive English.
- **Inline Audio Player**: Click `🔊 Listen` on any message card or executive report for on-demand audio narration.
- **Speech-to-Text (`🎙️ Mic`)**: Dictate questions directly into the input bar with live pulsation animation.

### 3. 📊 3-Tab Executive Workspace
- **Tab 1: `💬 BI Assistant`**: Main conversational AI workspace with glowing KPI ribbon, quick prompt chips, and Data Resilience Audit box.
- **Tab 2: `📊 Executive Reports`**: 1-click Weekly Leadership Briefing covering commercial velocity, operations delivery, cash flow risks, and recommendations.
- **Tab 3: `📁 Board Data`**: Live interactive records explorer with tab toggle between Deals (346 items) and Work Orders (176 items) with real-time text search.

### 4. ⚡ Live Monday.com Integration & Data Resilience
- **Zero Hardcoded CSVs**: All data dynamically queried from live Monday.com boards via GraphQL API v2.
- **120s Live Cache TTL Freshness**: Live countdown pill displaying data age.
- **Data Resilience Engine**: Normalizes inconsistent date formats (`YYYY-MM-DD`, `Dec`, Excel dates), sector aliases (`mining` $\rightarrow$ `Mining`), and imputed missing values ($0 for safe aggregations).
- **Data Quality (DQ) Audit**: Transparently caveats missing deal values and unbilled backlogs.

### 5. 🛡️ Comprehensive Error Handling & Fault Tolerance
- **Authentication Safeguards (`MondayAuthError`)**: Catches invalid/expired tokens (401/403) with clear resolution instructions.
- **Rate Limit Resilience (`MondayRateLimitError`)**: Handles HTTP 429 and GraphQL complexity limits with exponential backoff.
- **Stale Cache Fallback**: When network drops or Monday.com is unreachable, automatically serves cached board data.
- **Multi-tier LLM Fallback**: `gemini-3.6-flash` $\rightarrow$ `gemini-flash-latest` $\rightarrow$ `gemini-3.5-flash-lite` $\rightarrow$ Deterministic Rule Engine.

---

## 🛠️ Tech Stack

| Component | Technology | Role & Justification |
| :--- | :--- | :--- |
| **Backend Framework** | **Python 3.12+ / FastAPI** | High-performance async API with Pydantic type validation and REST endpoints. |
| **LLM & Reasoning** | **Google Gemini (`gemini-3.6-flash`)** | High-speed executive reasoning, contextual synthesis, and conversational fluency. |
| **Analytics Engine** | **Pandas & NumPy** | In-memory cross-board joins, exact financial aggregations, zero arithmetic error. |
| **Speech & Audio** | **Web Speech API (TTS & STT)** | Native browser speech synthesis & voice dictation without external audio latency. |
| **Frontend** | **Vanilla HTML5 / Modern Dark CSS / JS** | Fast, responsive glassmorphic 3-tab executive UI with zero build step dependencies. |
| **Integration** | **Monday.com GraphQL API v2** | Dynamic schema discovery, cursor pagination, and rate limit backoff. |

---

## 🚀 Quickstart & Setup

### Prerequisites
- Python 3.10+
- Valid `MONDAY_TOKEN` with access to your Monday.com workspace.
- Valid `GEMINI_API_KEY` for Google Gemini.

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/your-org/skylark-monday-bi-agent.git
cd skylark-monday-bi-agent
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Create or update `.env`:
```env
MONDAY_TOKEN=your_monday_token_here
WORKSPACE_ID=3364949
DEALS_BOARD_ID=5030846728
WORK_ORDERS_BOARD_ID=5030846665
GEMINI_API_KEY=your_gemini_api_key_here
CACHE_TTL_SECONDS=120
PORT=8000
```

### 3. Launch the Application
```bash
python -m uvicorn app.main:app --port 8000 --reload
```
Open your browser and navigate to: **`http://localhost:8000`**

---

## 🧪 Automated Testing

Run the full test suite (21 unit and integration tests):
```bash
python -m pytest -v
```

```
============================== 21 passed in 12.00s ==============================
```

---

## 📁 Repository Structure

```
skylark-monday-bi-agent/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI server, REST routes & global error handlers
│   ├── config.py                # Pydantic environment configuration
│   ├── monday_client.py         # Live Monday GraphQL client with retry & stale cache fallback
│   ├── data_cleaner.py          # Data resilience, date normalization & DQ auditor
│   ├── bi_engine.py             # Deterministic cross-board joins & financial aggregations
│   ├── agent.py                 # Gemini 3.6 Flash routing, ambiguity resolver & LLM fallbacks
│   ├── leadership_update.py     # Executive leadership briefing generator
│   └── static/                  # 3-Tab Executive UI
│       ├── index.html           # Layout with 3 tabs, 4 KPI cards, voice mic & chips
│       ├── style.css            # Dark glassmorphic design system
│       └── app.js               # Reactive tab switching, TTS voice engine, live search
├── tests/
│   ├── test_data_cleaner.py     # Data resilience & date parsing tests
│   ├── test_bi_engine.py        # KPI aggregations & cross-board join tests
│   ├── test_agent.py            # Intent classification & ambiguity detection tests
│   ├── test_api.py              # FastAPI REST endpoint tests
│   └── test_error_handling.py   # Auth, board not found, rate limit & cache fallback tests
├── scripts/
│   ├── seed_fast.py             # Script to populate Monday.com boards
│   └── check_progress.py        # Verification utility for live board records
├── Dockerfile                   # Cloud container build file
├── requirements.txt             # Python dependencies
├── README.md                    # Project documentation
└── DECISION_LOG.md              # Architectural decision log
```
