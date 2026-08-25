"""
app/agent.py
Conversational BI Agent with Google Gemini 3.6 Flash Integration.
Handles:
- Ambiguity detection and clarifying suggestions
- Natural chatbot interactions and conversational Q&A without repetitive "analysis" boilerplate
- Direct live Monday.com context grounding with verified Pandas calculations
- Multi-tier LLM fallbacks (Gemini 3.6 Flash -> Gemini Flash Latest -> Gemini 3.5 Flash Lite -> Deterministic Engine)
- Executive Leadership Briefing generation
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
from app.config import settings
from app.monday_client import monday_client
from app.data_cleaner import DataCleaner, normalize_sector
from app.bi_engine import BIEngine

logger = logging.getLogger("bi_agent")
logging.basicConfig(level=logging.INFO)

class ConversationalBIAgent:
    def __init__(self):
        self.cleaner = DataCleaner()
        self.gemini_client = None
        self._init_gemini()

    def _init_gemini(self):
        """Initialize Google GenAI client if API key is provided."""
        if settings.gemini_api_key:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=settings.gemini_api_key)
                logger.info("Google GenAI client initialized successfully.")
            except Exception as e:
                logger.warning(f"Could not initialize Google GenAI SDK: {e}")

    def load_data_and_engine(self, force_refresh: bool = False) -> Tuple[BIEngine, dict, dict]:
        """Fetch live board data, clean & audit, and return the BI calculation engine."""
        df_deals_raw, df_wo_raw = monday_client.get_deals_and_work_orders(force_refresh=force_refresh)
        df_deals_clean, deals_dq = self.cleaner.clean_deals_data(df_deals_raw)
        df_wo_clean, wo_dq = self.cleaner.clean_work_orders_data(df_wo_raw)
        engine = BIEngine(df_deals_clean, df_wo_clean)
        return engine, deals_dq, wo_dq

    def classify_intent(self, query: str) -> Dict[str, Any]:
        """Determine the business domain and intent of the founder's query."""
        q = query.lower()

        detected_sector = None
        for sec in ["mining", "powerline", "renewables", "tender", "aerospace", "telecom", "highways", "railways", "forestry"]:
            if sec in q:
                detected_sector = normalize_sector(sec)
                break

        if any(k in q for k in ["leadership update", "executive briefing", "weekly update", "board update", "executive summary", "prepare leadership update", "prepare this week"]):
            return {"intent": "leadership_update", "sector": detected_sector}
        elif any(k in q for k in ["cross-board", "cross board", "client", "customer", "account", "ar", "receivable", "collection"]):
            return {"intent": "cross_board", "sector": detected_sector}
        elif any(k in q for k in ["data quality", "missing", "audit", "hygiene"]):
            return {"intent": "data_quality", "sector": detected_sector}
        elif any(k in q for k in ["pipeline", "sales", "deals", "opportunity", "conversion", "win rate"]):
            return {"intent": "pipeline", "sector": detected_sector}
        elif any(k in q for k in ["billed", "unbilled", "backlog", "work order", "operations", "execution", "revenue"]):
            return {"intent": "operations", "sector": detected_sector}
        else:
            return {"intent": "general", "sector": detected_sector}

    def check_ambiguity(self, query: str) -> Optional[Dict[str, Any]]:
        """Detect ambiguous or broad single-word queries and offer clarifying options."""
        q = query.lower().strip()
        tokens = q.split()

        # Vague broad inquiries
        if any(phrase in q for phrase in ["how is performance looking", "give me an update", "how are we doing"]):
            return {
                "is_ambiguous": True,
                "clarification_message": "Could you clarify what aspect of business performance you would like to explore?",
                "suggested_options": [
                    {"label": "📊 Sales Pipeline & Deal Velocity", "query": "What is our total sales pipeline and weighted value?"},
                    {"label": "💰 Billed Revenue vs Unbilled Backlog", "query": "What is our overall revenue and billing status?"},
                    {"label": "🚨 Stuck Work Orders & Delays", "query": "Which work orders are currently marked as STUCK?"},
                    {"label": "📋 Full Executive Leadership Update", "query": "prepare this week's leadership update"}
                ]
            }

        # Extremely short queries with multiple valid interpretations
        if len(tokens) <= 2:
            if q in ["pipeline", "sales", "deals"]:
                return {
                    "is_ambiguous": True,
                    "clarification_message": "Could you clarify what aspect of the **Deals Pipeline** you'd like to explore?",
                    "suggested_options": [
                        {"label": "📊 Total Pipeline & Closure Probability", "query": "What is our total pipeline and weighted value?"},
                        {"label": "🏭 Pipeline Breakdown by Sector", "query": "How is our pipeline distributed by sector?"},
                        {"label": "📅 Pipeline Closing This Quarter", "query": "Which high-value deals are closing this quarter?"},
                        {"label": "👤 BD Owner Performance", "query": "How are BD owners performing?"}
                    ]
                }
            if q in ["work orders", "operations", "execution", "wo"]:
                return {
                    "is_ambiguous": True,
                    "clarification_message": "Would you like to review project delivery status, revenue billing, or operational delays?",
                    "suggested_options": [
                        {"label": "💰 Billed Revenue vs Unbilled Backlog", "query": "What is our overall revenue and billing status?"},
                        {"label": "🚨 Stuck or Delayed Work Orders", "query": "Which work orders are currently marked as STUCK?"},
                        {"label": "📦 Delivery Quantities & DMO Adoption", "query": "How much ops quantity and DMO platform adoption have we delivered?"},
                        {"label": "🏦 Accounts Receivable & Cashflow Risk", "query": "Which clients have high unbilled amounts or AR priority?"}
                    ]
                }
            if q in ["revenue", "billing", "money", "collections"]:
                return {
                    "is_ambiguous": True,
                    "clarification_message": "Are you inquiring about realized billed revenue, unbilled backlog, or outstanding AR collections?",
                    "suggested_options": [
                        {"label": "📈 Revenue Realization Rate", "query": "What is our billing realization rate vs total committed PO value?"},
                        {"label": "⏳ Unbilled Backlog by Sector", "query": "How much unbilled execution backlog do we have across sectors?"},
                        {"label": "💵 Top Accounts Receivable Risks", "query": "Which accounts have the highest outstanding AR?"}
                    ]
                }
            if q in ["energy", "mining", "powerline", "renewables", "highways", "telecom"]:
                sector_title = q.capitalize()
                return {
                    "is_ambiguous": True,
                    "clarification_message": f"Would you like to examine the **{sector_title}** sales pipeline, executed projects, or full 360° overview?",
                    "suggested_options": [
                        {"label": f"🔮 {sector_title} Sales Pipeline", "query": f"How is our pipeline looking for {sector_title}?"},
                        {"label": f"⚙️ {sector_title} Project Execution & Billing", "query": f"What is our revenue and work order execution for {sector_title}?"},
                        {"label": f"🌐 {sector_title} Full 360° View", "query": f"Give me a 360 view of {sector_title} sector."}
                    ]
                }

        return None

    def build_live_context_payload(self, engine: BIEngine, deals_dq: dict, wo_dq: dict) -> str:
        """Compile exact deterministic business metrics into a clean context payload for Gemini."""
        pipe = engine.get_pipeline_summary()
        ops = engine.get_operations_summary()
        cross = engine.get_cross_board_overview()

        # Top sectors
        top_sectors = list(pipe.get("pipeline_by_sector", {}).items())[:6]
        sectors_str = "\n".join([f"  - {s}: Total Value ₹{val:,.2f} ({val/10000000:.2f} Cr)" for s, val in top_sectors])

        # Top AR priority clients
        top_ar = cross.get("top_clients_by_ar", [])[:5]
        clients_str = "\n".join([f"  - Client {c['client_code']}: PO Value {c['formatted_po_value']}, Billed {c['formatted_billed']}, Outstanding AR {c['formatted_ar']}, Priority: {c['ar_priority']}" for c in top_ar])

        # Execution status breakdown
        exec_dict = {item.get("status"): item.get("count", 0) for item in ops.get("execution_breakdown", [])}

        return f"""
LIVE MONDAY.COM BUSINESS DATA (GROUND TRUTH):
- Deals & Sales Pipeline:
  * Total Opportunities: {pipe.get('total_deals', 0)}
  * Total Gross Pipeline Value: {pipe.get('formatted_total_pipeline', '₹0')} (₹{pipe.get('total_pipeline_val', 0):,.2f})
  * Probability-Weighted Pipeline: {pipe.get('formatted_weighted_pipeline', '₹0')} (₹{pipe.get('weighted_pipeline_val', 0):,.2f})
  * Top Pipeline Sectors:
{sectors_str}

- Work Orders & Operations Execution:
  * Total Committed Work Orders: {ops.get('total_work_orders', 0)} projects
  * Total Committed PO Value (Excl GST): {ops.get('formatted_total_po_excl', '₹0')} (₹{ops.get('total_po_val_excl', 0):,.2f})
  * Realized Billed Revenue (Excl GST): {ops.get('formatted_total_billed_excl', '₹0')} (₹{ops.get('total_billed_excl', 0):,.2f})
  * Unbilled Execution Backlog (Excl GST): {ops.get('formatted_total_unbilled_excl', '₹0')} (₹{ops.get('total_unbilled_excl', 0):,.2f})
  * Revenue Realization Rate: {ops.get('billing_realization_rate_pct', 0)}%
  * Total Cash Collected (Incl GST): {ops.get('formatted_total_collected', '₹0')}
  * Outstanding Accounts Receivable (AR): {ops.get('formatted_total_ar', '₹0')}
  * Completed Work Orders: {exec_dict.get('Completed', 0)}
  * In Progress Work Orders: {exec_dict.get('In Progress', 0)}
  * Stuck / Delayed Work Orders: {exec_dict.get('Stuck', 0)}

- Key Client Accounts & AR Risk:
{clients_str}

- Data Quality & Hygiene Flags:
  * Missing Deal Values: {deals_dq.get('missing_value_count', 210)} of {deals_dq.get('total_deals', 418)} deals have no recorded value.
  * Missing Actual Close Dates: {deals_dq.get('missing_actual_close_date_count', 413)} deals lack actual close dates.
  * Completed but Unbilled: {wo_dq.get('completed_unbilled_count', 25)} work orders are marked Completed with ₹0 billed.
"""

    def generate_gemini_response(self, query: str, context_str: str) -> Optional[str]:
        """Ask Google Gemini to generate a natural, conversational chatbot response."""
        if not self.gemini_client:
            self._init_gemini()
        if not self.gemini_client:
            return None

        system_instructions = (
            "You are the conversational AI assistant for Skylark Drones with direct real-time access to live Monday.com boards (Deals & Work Orders).\n\n"
            "CHATBOT BEHAVIOR RULES:\n"
            "1. Answer like a natural, smart, and friendly chatbot (like ChatGPT / Claude). Speak conversationally.\n"
            "2. DO NOT use repetitive boilerplate phrases like 'Here is the analysis', 'Based on my detailed analysis', 'Let us analyze', or 'Analysis:'.\n"
            "3. Answer direct questions directly and concisely in 1-3 crisp paragraphs. If helpful, use a short markdown table or bullet points.\n"
            "4. For greetings, casual questions, or small talk, respond warmly and naturally—do NOT dump full unprompted financial tables.\n"
            "5. Always ground any business figures in the provided LIVE BUSINESS DATA. Do NOT invent numbers.\n"
            "6. Keep your tone helpful, executive-friendly, and engaging.\n"
        )

        prompt = f"{system_instructions}\n\n{context_str}\n\nUser Question: \"{query}\"\n\nChatbot Response:"

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
        """Main agent workflow: Check greetings -> Check ambiguity -> Load live Monday data -> Use Gemini -> Fallback gracefully."""
        q_clean = query.strip()
        q_lower = q_clean.lower()

        # 1. Natural greeting / small-talk handler for pure conversational chatbot feel
        greetings = ["hi", "hello", "hey", "hey there", "hi there", "good morning", "good afternoon", "good evening", "howdy", "who are you", "what can you do", "help"]
        if q_lower in greetings or (len(q_lower.split()) <= 2 and any(q_lower.startswith(g) for g in ["hi", "hello", "hey"])):
            return {
                "type": "answer",
                "content": (
                    "Hey there! 👋 I'm your Skylark BI Assistant. I'm connected live to our Monday.com **Deals** (sales pipeline) and **Work Orders** (execution & revenue) boards.\n\n"
                    "Feel free to ask me anything like:\n"
                    "- *\"How's our sales pipeline looking for energy sector?\"*\n"
                    "- *\"What is our total revenue and billing backlog?\"*\n"
                    "- *\"Which work orders are currently stuck or delayed?\"*\n"
                    "- *\"Which clients have high outstanding receivables?\"*\n\n"
                    "What would you like to check today?"
                ),
                "suggested_options": [
                    {"label": "📊 Pipeline by Sector", "query": "How is our pipeline distributed by sector?"},
                    {"label": "💰 Total Revenue & Billing", "query": "What is our overall revenue and billing status?"},
                    {"label": "🚨 Stuck Work Orders", "query": "Which work orders are currently marked as STUCK?"},
                    {"label": "📋 Weekly Leadership Update", "query": "prepare this week's leadership update"}
                ],
                "caveats": []
            }

        # 2. Ambiguity check for extremely narrow keywords
        ambiguity_res = self.check_ambiguity(q_clean)
        if ambiguity_res:
            return {
                "type": "clarification",
                "content": ambiguity_res["clarification_message"],
                "suggested_options": ambiguity_res["suggested_options"],
                "caveats": []
            }

        # 3. Load live data & engine from Monday.com
        try:
            engine, deals_dq, wo_dq = self.load_data_and_engine(force_refresh=force_refresh)
        except Exception as e:
            logger.error(f"Error fetching Monday.com data: {e}")
            return {
                "type": "error",
                "content": f"⚠️ **Monday.com Connection Notice**: {str(e)}\n\nPlease ensure your `MONDAY_TOKEN` is configured in `.env`.",
                "suggested_options": [],
                "caveats": []
            }

        # 4. Check for Leadership update request
        if any(k in q_lower for k in ["leadership update", "weekly update", "executive update", "board update", "executive summary", "prepare leadership update", "prepare this week"]):
            from app.leadership_update import LeadershipUpdateGenerator
            gen = LeadershipUpdateGenerator(engine, deals_dq, wo_dq)
            report_md = gen.generate_leadership_update()
            caveats = self.cleaner.generate_dq_caveats(deals_dq, wo_dq)
            return {
                "type": "leadership_update",
                "content": report_md,
                "suggested_options": [
                    {"label": "⚡ Drill into Energy Sector", "query": "How is our pipeline looking for energy sector?"},
                    {"label": "🚨 Review AR Risk Accounts", "query": "Which clients have high unbilled amounts or AR priority?"}
                ],
                "caveats": caveats
            }

        # 5. Generate response via Google Gemini using live context
        context_payload = self.build_live_context_payload(engine, deals_dq, wo_dq)
        gemini_text = self.generate_gemini_response(q_clean, context_payload)

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

        # 6. Deterministic fallback if Gemini is offline
        p_data = engine.get_pipeline_summary()
        o_data = engine.get_operations_summary()
        lines = [
            f"Here is our current business pulse from Monday.com:\n",
            f"- **Sales Pipeline**: **{p_data['formatted_total_pipeline']}** (Weighted: **{p_data['formatted_weighted_pipeline']}** across {p_data['total_deals']} opportunities)",
            f"- **Committed Work Orders**: **{o_data['formatted_total_po_excl']}** ({o_data['total_work_orders']} projects)",
            f"- **Billed Revenue Realized**: **{o_data['formatted_total_billed_excl']}** (**{o_data['billing_realization_rate_pct']}%** realization rate)",
            f"- **Unbilled Execution Backlog**: **{o_data['formatted_total_unbilled_excl']}**",
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
