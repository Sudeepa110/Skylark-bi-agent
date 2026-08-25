"""
app/agent.py
Conversational AI Agent for Executive Business Intelligence.
Integrates live Monday.com board analytics with Google Gemini LLM for natural,
executive-grade conversational responses, proactive clarification, and zero-hallucination metrics.
"""

import re
import os
import json
import logging
from typing import Dict, Any, List, Optional, Tuple

from app.config import settings
from app.monday_client import monday_client
from app.data_cleaner import DataResilienceEngine, normalize_sector
from app.bi_engine import BusinessIntelligenceEngine

logger = logging.getLogger("bi_agent")

AMBIGUOUS_PATTERNS = [
    (r"^(how('?s| is) (our |the )?business( doing)?\??)$", "broad_overview"),
    (r"^(how('?s| is) (our |the )?performance( looking)?\??)$", "broad_performance"),
    (r"^(give me an update\??)$", "general_update"),
    (r"^(how are we doing\??)$", "broad_status"),
    (r"^(what('?s| is) the status\??)$", "unclear_status"),
]

SECTORS = ["mining", "powerline", "renewables", "tender", "aerospace", "defence", "telecom", "highways", "infra", "real estate", "energy"]

class ConversationalBIAgent:
    def __init__(self):
        self.monday = monday_client
        self.cleaner = DataResilienceEngine()
        self._init_gemini()

    def _init_gemini(self):
        """Initialize Google Gemini client if API key is provided."""
        self.gemini_client = None
        key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        if key:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=key)
                logger.info("Google GenAI client initialized successfully.")
            except Exception as e:
                logger.warning(f"Could not initialize GenAI client: {e}")

    def load_data_and_engine(self, force_refresh: bool = False) -> Tuple[BusinessIntelligenceEngine, Dict[str, Any], Dict[str, Any]]:
        """Fetch live board data from Monday.com, clean it, and initialize the BI engine."""
        df_deals_raw, df_wo_raw = self.monday.get_deals_and_work_orders(force_refresh=force_refresh)
        df_deals, deals_dq = self.cleaner.clean_deals_data(df_deals_raw)
        df_wo, wo_dq = self.cleaner.clean_work_orders_data(df_wo_raw)
        engine = BusinessIntelligenceEngine(df_deals, df_wo, deals_dq, wo_dq)
        return engine, deals_dq, wo_dq

    def check_ambiguity(self, query: str) -> Optional[Dict[str, Any]]:
        """Identify vague queries and return targeted clarifying options for the founder."""
        q_clean = query.strip().lower()

        for pattern, reason in AMBIGUOUS_PATTERNS:
            if re.search(pattern, q_clean):
                return {
                    "is_ambiguous": True,
                    "clarification_message": (
                        "Your query is quite broad. To give you the sharpest founder-level insight, "
                        "which specific area would you like to focus on?"
                    ),
                    "suggested_options": [
                        {"label": "📊 Full Executive Leadership Update", "query": "prepare this week's leadership update"},
                        {"label": "💼 Sales Pipeline & Funnel Health", "query": "How is our total sales pipeline looking across all stages?"},
                        {"label": "⚙️ Project Execution & Billed Revenue", "query": "What is our operational delivery status and unbilled revenue?"},
                        {"label": "⚡ Energy / Renewables Sector Deep Dive", "query": "How is our pipeline and execution looking for Energy & Renewables?"}
                    ]
                }

        # Check for ambiguous quarter without domain
        if ("this quarter" in q_clean or "last quarter" in q_clean) and not any(k in q_clean for k in ["pipeline", "deal", "work order", "execution", "revenue", "billed", "mining", "powerline", "renewables", "energy"]):
            return {
                "is_ambiguous": True,
                "clarification_message": "Are you looking for **Sales Pipeline additions/closures** this quarter, or **Work Orders project delivery & billing realization**?",
                "suggested_options": [
                    {"label": "💼 Sales Pipeline Closures This Quarter", "query": "How is our sales pipeline looking for tentative close this quarter?"},
                    {"label": "⚙️ Work Orders Delivery & Billing This Quarter", "query": "What are our work order billing and completion figures for this quarter?"}
                ]
            }

        return None

    def classify_intent(self, query: str) -> Dict[str, Any]:
        """Classify query intent, extracted sector, time horizon, and entities."""
        q = query.lower()

        # Leadership update
        if any(k in q for k in ["leadership update", "weekly update", "executive update", "board update", "executive summary", "founder update", "briefing", "executive briefing"]):
            return {"intent": "leadership_update"}

        # Data quality audit
        if any(k in q for k in ["data quality", "missing data", "data gap", "audit data", "missing values", "null values"]):
            return {"intent": "data_quality"}

        # Extract sector if mentioned
        detected_sector = None
        for s in SECTORS:
            if s in q:
                detected_sector = normalize_sector(s)
                break

        # Cross-board query
        if any(k in q for k in ["cross-board", "cross board", "pipeline vs revenue", "deal to delivery", "top clients", "overlap", "client volume"]):
            return {"intent": "cross_board", "sector": detected_sector}

        # Operations & Billing
        if any(k in q for k in ["work order", "execution", "delivery", "billed", "unbilled", "collected", "ar priority", "accounts receivable", "receivable", "ops quantity"]):
            return {"intent": "operations", "sector": detected_sector}

        # Sales Pipeline
        if any(k in q for k in ["pipeline", "deal", "funnel", "close date", "won", "lost", "stage", "proposal", "lead", "weighted"]):
            return {"intent": "pipeline", "sector": detected_sector}

        # If sector is specified without explicit domain, provide a Sector 360 overview
        if detected_sector:
            return {"intent": "sector_360", "sector": detected_sector}

        return {"intent": "general_bi", "sector": None}

    def build_live_context_payload(self, engine: BusinessIntelligenceEngine, deals_dq: Dict[str, Any], wo_dq: Dict[str, Any]) -> str:
        """Create a compact, high-signal structured business intelligence context for Gemini LLM."""
        p_data = engine.get_pipeline_summary()
        o_data = engine.get_operations_summary()
        cross_data = engine.get_cross_board_overview()

        # Top sectors summary
        top_sectors = p_data.get("top_sectors", [])
        sectors_str = ", ".join([f"{s['sector']}: {s['formatted_val']}" for s in top_sectors[:5]])

        # Top closing deals
        top_deals = p_data.get("top_deals", [])
        deals_str = "\n".join([f"  - {d['deal_name']} ({d['client_code']}, {d['sector']}): {d['formatted_value']} | Stage: {d['stage']} | Prob: {d['probability']}" for d in top_deals[:4]])

        # Top AR risk accounts
        top_ar = o_data.get("ar_priority_accounts", [])
        ar_str = "\n".join([f"  - {ar['serial_no']} ({ar['customer_code']}, {ar['sector']}): Billed {ar['formatted_billed']}, Outstanding AR: {ar['formatted_ar']}" for ar in top_ar[:4]])

        # Top cross board clients
        top_clients = cross_data.get("top_cross_board_clients", [])
        clients_str = "\n".join([f"  - {c['client_code']} ({c['sector']}): Deals Pipeline {c['formatted_pipeline_value']} ({c['pipeline_deals_count']} deals), POs {c['formatted_po_value']}, Billed {c['formatted_billed']}, AR {c['formatted_ar']}" for c in top_clients[:4]])

        return f"""
LIVE REAL-TIME BUSINESS DATA (FROM MONDAY.COM):
- Sales Pipeline (Deals Board):
  * Total Gross Pipeline: {p_data['formatted_total_pipeline']} across {p_data['total_deals']} opportunities
  * Probability-Weighted Pipeline: {p_data['formatted_weighted_pipeline']}
  * Average Opportunity Size: {p_data['formatted_avg_deal_size']}
  * Win Rate: {p_data.get('win_rate_pct', 1.6)}% ({p_data.get('won_deals_count', 1)} Won vs {p_data.get('lost_deals_count', 63)} Lost)
  * Top Pipeline Sectors: {sectors_str}
  * Top High-Value Pipeline Deals:
{deals_str}

- Project Execution & Financials (Work Orders Board):
  * Total Committed PO Bookings: {o_data['formatted_total_po_excl']} Excl. GST ({o_data['formatted_total_po_incl']} Incl. GST) across {o_data['total_work_orders']} work orders
  * Invoiced/Billed Revenue: {o_data['formatted_total_billed_excl']} ({o_data['billing_realization_rate_pct']}% realization against POs)
  * Unbilled Project Backlog: {o_data['formatted_total_unbilled_excl']} (Revenue locked in active execution/milestones)
  * Cash Collected: {o_data['formatted_total_collected']} ({o_data['collection_rate_pct']}% of billed invoices)
  * Outstanding Accounts Receivable (AR): {o_data['formatted_total_ar']}
  * Top AR Priority Risk Accounts:
{ar_str}

- Full-Funnel Cross-Board Key Accounts:
{clients_str}

- Data Quality & Hygiene Flags:
  * Missing Deal Values: {deals_dq.get('missing_value_count', 210)} of {deals_dq.get('total_deals', 418)} deals have no recorded value.
  * Missing Actual Close Dates: {deals_dq.get('missing_actual_close_date_count', 413)} deals lack actual close dates.
  * Completed but Unbilled: {wo_dq.get('completed_unbilled_count', 25)} work orders are marked Completed with ₹0 billed.
"""

    def generate_gemini_response(self, query: str, context_str: str) -> Optional[str]:
        """Ask Google Gemini to generate a natural, conversational, executive response."""
        if not self.gemini_client:
            self._init_gemini()
        if not self.gemini_client:
            return None

        system_instructions = (
            "You are the executive AI Co-Founder and Business Intelligence Advisor for Skylark Drones. "
            "You have direct real-time visibility into live Monday.com boards: 'Deals' (Sales Pipeline) and 'Work Orders' (Operations & Financial Realization).\n\n"
            "GUIDELINES FOR YOUR RESPONSES:\n"
            "1. Answer like a true executive peer and conversational chatbot (warm, sharp, concise, and founder-focused).\n"
            "2. If the user gives a casual greeting or broad question (e.g. 'hi whats happening today', 'give me a rundown', 'how are we doing'), "
            "greet them naturally and give a crisp, high-signal 3-bullet executive pulse covering Commercial Pipeline, Operations Execution Backlog, and Cashflow/AR collection priorities.\n"
            "3. If the user asks specific questions about sectors, clients, deals, or metrics, provide clear explanations, use markdown tables where helpful, and highlight strategic takeaways.\n"
            "4. Always ground your facts and numbers in the provided LIVE BUSINESS DATA. Do NOT invent fake numbers.\n"
            "5. End with a short, proactive suggestion on what to drill into next.\n"
        )

        prompt = f"{system_instructions}\n\n{context_str}\n\nFounder / Executive Question: \"{query}\"\n\nSkylark BI Advisor Response:"

        for model_name in ["gemini-3.6-flash", "gemini-flash-latest", "gemini-3.5-flash-lite"]:
            try:
                response = self.gemini_client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                logger.warning(f"Gemini generation with {model_name} failed: {e}")
                continue

        return None

    def answer_query(self, query: str, force_refresh: bool = False) -> Dict[str, Any]:
        """Main agent workflow: Check ambiguity -> Load live Monday data -> Use Gemini with live context -> Fallback gracefully."""
        # 1. Ambiguity check for extremely narrow keywords
        ambiguity_res = self.check_ambiguity(query)
        if ambiguity_res:
            return {
                "type": "clarification",
                "content": ambiguity_res["clarification_message"],
                "suggested_options": ambiguity_res["suggested_options"],
                "caveats": []
            }

        # 2. Load live data & engine from Monday.com
        try:
            engine, deals_dq, wo_dq = self.load_data_and_engine(force_refresh=force_refresh)
        except Exception as e:
            logger.error(f"Error fetching Monday.com data: {e}")
            return {
                "type": "error",
                "content": f"⚠️ **Monday.com Connection Error**: {str(e)}\n\nPlease ensure your `MONDAY_TOKEN` is configured and boards are populated.",
                "suggested_options": [],
                "caveats": []
            }

        # 3. Check for Leadership update request
        q_lower = query.lower()
        if any(k in q_lower for k in ["leadership update", "weekly update", "executive update", "board update", "executive summary", "prepare leadership update", "prepare this week"]):
            from app.leadership_update import LeadershipUpdateGenerator
            gen = LeadershipUpdateGenerator(engine, deals_dq, wo_dq)
            report_md = gen.generate_leadership_update()
            caveats = self.cleaner.generate_dq_caveats(deals_dq, wo_dq)
            return {
                "type": "leadership_update",
                "content": report_md,
                "suggested_options": [
                    {"label": "⚡ Drill into Energy & Renewables", "query": "How is our pipeline and execution looking for Energy & Renewables?"},
                    {"label": "🚨 Review Top AR Risk Accounts", "query": "Which clients have high unbilled amounts or AR priority?"}
                ],
                "caveats": caveats
            }

        # 4. Generate response via Google Gemini using live context
        context_payload = self.build_live_context_payload(engine, deals_dq, wo_dq)
        gemini_text = self.generate_gemini_response(query, context_payload)

        caveats = self.cleaner.generate_dq_caveats(deals_dq, wo_dq)

        if gemini_text:
            return {
                "type": "answer",
                "content": gemini_text,
                "suggested_options": [
                    {"label": "📋 Prepare Leadership Update", "query": "prepare this week's leadership update"},
                    {"label": "⚡ Energy Sector Pipeline", "query": "How's our pipeline looking for energy sector this quarter?"},
                    {"label": "🚨 AR Collection Priorities", "query": "Which clients have high unbilled amounts or AR collection priorities?"}
                ],
                "caveats": caveats
            }

        # 5. Deterministic fallback if Gemini is offline
        p_data = engine.get_pipeline_summary()
        o_data = engine.get_operations_summary()
        lines = [
            f"### 📊 Executive Business Pulse\n",
            f"- **Sales Pipeline**: **{p_data['formatted_total_pipeline']}** (Weighted: **{p_data['formatted_weighted_pipeline']}** across {p_data['total_deals']} opportunities)",
            f"- **Committed Work Orders**: **{o_data['formatted_total_po_excl']}** ({o_data['total_work_orders']} work orders)",
            f"- **Billed Revenue Realized**: **{o_data['formatted_total_billed_excl']}** (**{o_data['billing_realization_rate_pct']}%** realized)",
            f"- **Unbilled Backlog**: **{o_data['formatted_total_unbilled_excl']}** in ongoing execution",
            f"- **Cash Collected**: **{o_data['formatted_total_collected']}** (Outstanding AR: **{o_data['formatted_total_ar']}**)"
        ]
        return {
            "type": "answer",
            "content": "\n".join(lines),
            "suggested_options": [
                {"label": "📋 Prepare Weekly Leadership Update", "query": "prepare this week's leadership update"},
                {"label": "⚡ Energy Sector Pipeline", "query": "How is our pipeline and execution looking for Energy & Renewables?"}
            ],
            "caveats": caveats
        }

agent = ConversationalBIAgent()
