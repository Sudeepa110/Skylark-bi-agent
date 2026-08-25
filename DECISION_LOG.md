# 📋 Architectural Decision Log: Monday.com Business Intelligence Agent

**Author**: Skylark Engineering & Antigravity AI  
**Date**: August 2026  
**Assignment**: Skylark Drones Technical Assignment — Founder-Level Monday.com Business Intelligence Agent  

---

## 1. Key Assumptions

1. **Entity Resolution & Cross-Board Linkage**:
   - The **Deals** board uses `Client Code` (e.g. `COMPANY089`), whereas the **Work Orders** board uses `Customer Name Code` (e.g. `WOCOMPANY_089`). We strip the `WO` prefix and standardize casing/delimiters to create a deterministic primary key (`COMPANY089`) for full-funnel client account reconciliation.
   - For deal-level linkage, `Deal Name` in Deals correlates directly to `Deal name masked` in Work Orders.

2. **Temporal Horizons & Fiscal Quarter Mapping**:
   - Dates in Deals and Work Orders span FY24 through FY26. Inquiries referencing *"this quarter"* or specific quarters map dynamically to calendar/fiscal quarters based on the item's `actual_close_date` or fallback `tentative_close_date` for Deals, and `date_of_po` for Work Orders.
   - Where actual close dates are missing (~91.9% of deal records), tentative close dates are utilized with an explicit Data Quality (DQ) warning to the founder.

3. **Financial Realization & Currency Standards**:
   - All masked financial values are in Indian Rupees (₹) and formatted in Crores (Cr) / Lakhs (L) for founder legibility.
   - `Amount in Rupees (Excl of GST)` represents the committed purchase order baseline.
   - `Unbilled Revenue Backlog` is computed as `Amount Excl. GST - Billed Value Excl. GST`.
   - `Outstanding Accounts Receivable (AR)` is computed as `Billed Value Incl. GST - Collected Amount Incl. GST`.
   - Deals with null or `$0` masked values are imputed to `₹0` for mathematical aggregations but retained in volume/stage funnel metrics, accompanied by a transparent Data Quality caveat.

4. **Probability Weighting**:
   - Probability categories (`High`, `Medium`, `Low`) map to standard commercial multipliers ($0.80$, $0.50$, $0.20$; default $0.30$) to compute risk-adjusted pipeline projections.

---

## 2. Trade-offs Chosen and Rationale

| Architecture Dimension | Chosen Approach | Alternative Considered | Rationale & Trade-off |
| :--- | :--- | :--- | :--- |
| **LLM & Calculation Engine** | **Deterministic In-Memory Pandas Engine + Google Gemini 3.6 Flash Framing** | Pure LLM Code-Gen / Text-to-Pandas | Pure LLM code generation frequently hallucinates financial arithmetic, divides by zero on missing values, and adds latency. Our hybrid architecture computes mathematically verified numbers in Python and feeds them into Gemini 3.6 Flash purely for executive framing, trend analysis, and strategic advice. |
| **Multi-Tier LLM Resilience** | **`gemini-3.6-flash` $\rightarrow$ `gemini-flash-latest` $\rightarrow$ `gemini-3.5-flash-lite` $\rightarrow$ Deterministic Rules** | Single-Model Hard Dependency | If Google Gemini experiences high demand or temporary 503 errors, the client cascades automatically down fallback tiers, guaranteeing the founder always gets an immediate, verified business answer. |
| **Data Synchronization** | **Live GraphQL Fetching with 120s TTL In-Memory Cache & Stale Cache Fallback** | Full Database ETL Mirror (Postgres / SQLite) | Mirroring to an external database introduces sync drift and violates the live read requirement. A 120s in-memory TTL protects against Monday.com complexity rate limits while preserving live data freshness. Stale cache fallback ensures zero downtime during temporary network blips. |
| **User Experience & Navigation** | **3-Tab Executive Workspace (BI Assistant, Reports, Board Data)** | Single-stream monolithic chatbot | Founder workflows require both conversational ad-hoc drilling and structured high-level briefings. Separating into 3 specialized tabs provides instant access to weekly briefings and live board grids without cluttering the chat feed. |
| **Voice Synthesis (TTS / STT)** | **Native Browser Web Speech API** | Cloud TTS APIs (ElevenLabs / Google Cloud TTS) | Web Speech API provides instantaneous, zero-latency speech synthesis and voice dictation directly inside the browser with zero external per-character API costs or network lag. |
| **Fault Tolerance & Error Classification** | **Hierarchical Custom Exception Handlers (`MondayAuthError`, `MondayBoardNotFoundError`, etc.)** | Generic 500 Server Errors | Providing structured error types with explicit founder-facing resolution steps allows users to immediately understand how to fix misconfigured tokens, board permissions, or network issues. |

---

## 3. What We Would Do Differently With More Time

1. **Semantic Embeddings & Hybrid Vector Search**:
   - Integrate vector embeddings (e.g., pgvector or ChromaDB) over work order delivery remarks, invoice details, and deal notes to answer qualitative inquiries (e.g., *"Why did powerline inspections stall for client COMPANY038?"*).

2. **Automated Monday.com Writeback & Actions**:
   - Allow founders to trigger actions directly from the chat interface (e.g., *"Tag client COMPANY002 as AR Priority on Monday"* or *"Send follow-up reminder to OWNER_002 for missing close dates"*).

3. **Multi-Tenant OAuth 2.0 Integration**:
   - Transition from static `MONDAY_TOKEN` to full OAuth 2.0 Monday app integration with role-based access control (RBAC), allowing department heads to view board data scoped to their permissions.

4. **Automated Threshold Alerts & Slack Webhooks**:
   - Deploy background workers (Celery/Redis) that monitor critical risk triggers (e.g., work orders completed >30 days ago with ₹0 billed) and broadcast automated Slack digests.

---

## 4. Structure of "Executive Leadership Updates"

In a high-growth technology and operations company like Skylark Drones, founders and executive teams need a high-signal, zero-fluff digest. We structured the **Executive Leadership Update** into six functional pillars:

1. **Executive Scorecard**: High-level KPIs contrasting Gross Pipeline vs. Weighted Pipeline alongside Booked PO Volume, Billed Revenue Realization Rate, and Outstanding Receivables.
2. **Sales Velocity & Commercial Funnel**: Win rates, stage conversion distribution, top-performing sectors, and top 3 high-probability closing deals.
3. **Project Execution & Operations**: Completed vs. In Progress vs. Not Started project breakdown, ops quantities delivered, and software deliverable (Spectra/DMO) adoption.
4. **Revenue Realization & Cashflow Health**: Analysis of the unbilled project backlog and immediate identification of top AR priority accounts with high outstanding balances.
5. **Data Quality & Transparency Alerts**: Proactively flags operational blind spots (e.g., deals missing values or completed work orders lacking invoices).
6. **Actionable Weekly Tactical Recommendations**: Direct, prioritized action items for Sales Leadership (deal acceleration), Operations (billing unblocked), and Finance (DSO reduction).
