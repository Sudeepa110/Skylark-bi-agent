"""
app/leadership_update.py
Automated Executive Leadership Update Generator.
Synthesizes high-level KPIs, sales velocity, project delivery health,
revenue realization, cashflow risks, and actionable recommendations across both boards.
"""

from typing import Dict, Any
from app.bi_engine import BusinessIntelligenceEngine

class LeadershipUpdateGenerator:
    def __init__(self, engine: BusinessIntelligenceEngine, deals_dq: dict, wo_dq: dict):
        self.engine = engine
        self.deals_dq = deals_dq
        self.wo_dq = wo_dq

    def generate_leadership_update(self) -> str:
        """Produce a comprehensive executive briefing for weekly leadership / board meetings."""
        p_data = self.engine.get_pipeline_summary()
        o_data = self.engine.get_operations_summary()
        cross_data = self.engine.get_cross_board_overview()

        lines = []
        lines.append("# 🚀 Founder & Executive Leadership Update\n")
        lines.append("> **Confidential Executive Briefing** | *Generated live from Monday.com Work Orders & Deals Boards*\n")

        # 1. Executive Scorecard
        lines.append("## 📊 1. Executive Scorecard & Key Metrics\n")
        lines.append("| Metric | Value | Context / Health |")
        lines.append("| :--- | :---: | :--- |")
        lines.append(f"| **Gross Sales Pipeline** | **{p_data['formatted_total_pipeline']}** | Across {p_data['total_deals']} active opportunities |")
        lines.append(f"| **Weighted Pipeline (Prob-Adjusted)** | **{p_data['formatted_weighted_pipeline']}** | High-confidence conversion pipeline |")
        lines.append(f"| **Committed PO Bookings** | **{o_data['formatted_total_po_excl']}** | {o_data['total_work_orders']} Work orders (Excl. GST) |")
        lines.append(f"| **Invoiced Revenue to Date** | **{o_data['formatted_total_billed_excl']}** | **{o_data['billing_realization_rate_pct']}%** of total committed POs billed |")
        lines.append(f"| **Unbilled Project Backlog** | **{o_data['formatted_total_unbilled_excl']}** | Revenue locked in execution / milestones |")
        lines.append(f"| **Cash Collections** | **{o_data['formatted_total_collected']}** | **{o_data['collection_rate_pct']}%** collection against billed invoices |")
        lines.append(f"| **Outstanding Accounts Receivable (AR)** | **{o_data['formatted_total_ar']}** | Total pending collection exposure |")

        # 2. Sales Pipeline & Commercial Velocity
        lines.append("\n## 💼 2. Sales Pipeline & Commercial Velocity")
        lines.append(f"- **Win Rate**: **{p_data['win_rate_pct']}%** among closed opportunities ({p_data['won_deals_count']} Won vs {p_data['lost_deals_count']} Lost).")
        lines.append(f"- **Average Deal Size**: **{p_data['formatted_avg_deal_size']}** for recorded opportunities.")
        
        # Sector ranking
        if p_data.get("sectors"):
            top_sectors = p_data["sectors"][:4]
            sec_summary = ", ".join([f"**{s['sector']}** ({s['formatted_value']})" for s in top_sectors])
            lines.append(f"- **Top Pipeline Sectors**: {sec_summary}.")

        # Top 3 High-Value Pipeline Deals
        if p_data.get("top_deals"):
            lines.append("\n### 🎯 Top Closing Opportunities")
            lines.append("| Deal Name | Client Code | Sector | Stage | Value | Probability | Tentative Close |")
            lines.append("| :--- | :--- | :--- | :--- | :---: | :---: | :---: |")
            for d in p_data["top_deals"][:3]:
                lines.append(f"| {d['deal_name']} | `{d['client_code']}` | {d['sector']} | {d['stage']} | **{d['formatted_value']}** | {d['probability']} | {d['tentative_close']} |")

        # 3. Project Execution & Delivery Health
        lines.append("\n## ⚙️ 3. Project Delivery & Operations")
        if o_data.get("execution_breakdown"):
            lines.append("| Execution Milestone | Work Orders Count | Total Value (Excl. GST) | Unbilled Exposure |")
            lines.append("| :--- | :---: | :---: | :---: |")
            for eb in o_data["execution_breakdown"]:
                lines.append(f"| **{eb['status']}** | {eb['count']} | {eb['formatted_po_value']} | {eb['formatted_unbilled']} |")

        # 4. Financial Realization & Collections Risk
        lines.append("\n## 💰 4. Cash Flow & Working Capital Risk")
        lines.append(f"- **Unbilled Backlog**: **{o_data['formatted_total_unbilled_excl']}** is awaiting milestone sign-offs or invoice generation.")
        lines.append(f"- **Total Outstanding Receivables**: **{o_data['formatted_total_ar']}** across active and completed work orders.")
        
        if o_data.get("ar_priority_accounts"):
            lines.append("\n### 🚨 High-Priority Collections Attention")
            lines.append("| Serial # | Customer | Sector | Billed (Incl. GST) | Collected | **Outstanding AR** |")
            lines.append("| :--- | :--- | :--- | :---: | :---: | :---: |")
            for ar in o_data["ar_priority_accounts"][:4]:
                lines.append(f"| `{ar['serial_no']}` | `{ar['customer_code']}` | {ar['sector']} | {ar['formatted_billed']} | {ar['formatted_collected']} | **{ar['formatted_ar']}** |")

        # 5. Top Strategic Recommendations
        lines.append("\n## 🎯 5. Recommended Leadership Action Items")
        lines.append("1. **Sales Leadership**: Accelerate commercial negotiation on top deals in *Proposal / Commercials Sent* stage to convert ~₹10Cr+ into booking orders before quarter end.")
        lines.append("2. **Operations Leadership**: Resolve execution bottlenecks on completed work orders with ₹0 billed to trigger immediate invoice dispatch.")
        lines.append("3. **Finance & Collections**: Initiate executive escalation on top AR accounts to recover high outstanding receivables and reduce DSO.")

        return "\n".join(lines)
