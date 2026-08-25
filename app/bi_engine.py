"""
app/bi_engine.py
Deterministic Business Intelligence and Cross-Board Analytics Engine.
Performs exact statistical aggregations, cross-board joins, sector drilldowns,
and executive financial realization metrics across Deals and Work Orders.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from app.data_cleaner import normalize_sector

class BusinessIntelligenceEngine:
    def __init__(self, df_deals: pd.DataFrame, df_wo: pd.DataFrame, deals_dq: dict = None, wo_dq: dict = None):
        self.df_deals = df_deals.copy() if not df_deals.empty else pd.DataFrame()
        self.df_wo = df_wo.copy() if not df_wo.empty else pd.DataFrame()
        self.deals_dq = deals_dq or {}
        self.wo_dq = wo_dq or {}

    # -------------------------------------------------------------------------
    # FORMATTING UTILS
    # -------------------------------------------------------------------------
    @staticmethod
    def format_currency(val: float) -> str:
        """Format number into Indian Rupee representation (Lakhs / Crores / Thousands)."""
        if pd.isna(val) or val == 0:
            return "₹0"
        abs_val = abs(val)
        sign = "-" if val < 0 else ""
        if abs_val >= 10000000:
            return f"{sign}₹{abs_val / 10000000:.2f} Cr"
        elif abs_val >= 100000:
            return f"{sign}₹{abs_val / 100000:.2f} L"
        elif abs_val >= 1000:
            return f"{sign}₹{abs_val / 1000:.1f} K"
        else:
            return f"{sign}₹{abs_val:.2f}"

    # -------------------------------------------------------------------------
    # 1. SALES PIPELINE ANALYTICS
    # -------------------------------------------------------------------------
    def get_pipeline_summary(self, sector_filter: Optional[str] = None, quarter_filter: Optional[str] = None, owner_filter: Optional[str] = None) -> Dict[str, Any]:
        """Aggregate sales pipeline metrics with optional sector/quarter/owner filters."""
        df = self.df_deals.copy()
        if df.empty:
            return {
                "total_deals": 0, "total_pipeline_val": 0, "weighted_pipeline_val": 0,
                "formatted_total_pipeline": "₹0", "formatted_weighted_pipeline": "₹0",
                "avg_deal_size": 0, "formatted_avg_deal_size": "₹0", "win_rate_pct": 0,
                "won_deals_count": 0, "lost_deals_count": 0, "stages": [], "sectors": [], "top_deals": []
            }

        # Apply filters
        if sector_filter and sector_filter.lower() != "all":
            df = df[df["sector"].str.lower() == sector_filter.lower()]
            
        if quarter_filter and quarter_filter.lower() != "all":
            df = df[df["close_quarter"].str.lower() == quarter_filter.lower()]

        if owner_filter and owner_filter.lower() != "all":
            df = df[df["owner_code"].str.upper() == owner_filter.upper()]

        total_deals = len(df)
        deals_with_val = df[df["deal_value"] > 0]
        total_pipeline_val = float(df["deal_value"].sum()) if not df.empty else 0.0
        weighted_pipeline_val = float(df["weighted_deal_value"].sum()) if not df.empty else 0.0
        avg_deal_size = float(deals_with_val["deal_value"].mean()) if len(deals_with_val) > 0 else 0.0

        # Stage breakdown
        stage_records = []
        if not df.empty and "stage_category" in df.columns:
            stage_group = df.groupby("stage_category", observed=False).agg(
                deal_count=("deal_name", "count"),
                pipeline_value=("deal_value", "sum"),
                weighted_value=("weighted_deal_value", "sum")
            ).reset_index()

            for _, row in stage_group.iterrows():
                stage_records.append({
                    "stage": row["stage_category"],
                    "count": int(row["deal_count"]),
                    "value": float(row["pipeline_value"]),
                    "formatted_value": self.format_currency(row["pipeline_value"]),
                    "weighted_value": float(row["weighted_value"]),
                    "formatted_weighted": self.format_currency(row["weighted_value"])
                })

        # Sector breakdown
        sector_records = []
        if not df.empty and "sector" in df.columns:
            sector_group = df.groupby("sector", observed=False).agg(
                deal_count=("deal_name", "count"),
                pipeline_value=("deal_value", "sum"),
                weighted_value=("weighted_deal_value", "sum")
            ).reset_index().sort_values(by="pipeline_value", ascending=False)

            for _, row in sector_group.iterrows():
                sector_records.append({
                    "sector": row["sector"],
                    "count": int(row["deal_count"]),
                    "value": float(row["pipeline_value"]),
                    "formatted_value": self.format_currency(row["pipeline_value"]),
                    "weighted_value": float(row["weighted_value"]),
                    "formatted_weighted": self.format_currency(row["weighted_value"])
                })

        # Top 5 high-value opportunities
        top_deals = []
        if not df.empty:
            for _, row in df.sort_values(by="deal_value", ascending=False).head(5).iterrows():
                if row["deal_value"] > 0:
                    top_deals.append({
                        "deal_name": row["deal_name"],
                        "client_code": row["client_code_raw"],
                        "sector": row["sector"],
                        "stage": row["clean_deal_stage"],
                        "owner": row["owner_code"],
                        "value": float(row["deal_value"]),
                        "formatted_value": self.format_currency(row["deal_value"]),
                        "probability": f"{int(row['probability_pct'] * 100)}%",
                        "tentative_close": str(row["effective_close_dt"].strftime("%Y-%m-%d")) if pd.notna(row["effective_close_dt"]) else "Not set"
                    })

        # Win Rate
        won_cnt = int((df["stage_category"] == "Won").sum()) if "stage_category" in df.columns else 0
        lost_cnt = int((df["stage_category"] == "Lost").sum()) if "stage_category" in df.columns else 0
        closed_total = won_cnt + lost_cnt
        win_rate = round((won_cnt / closed_total * 100), 1) if closed_total > 0 else 0.0

        return {
            "total_deals": total_deals,
            "deals_with_value_count": len(deals_with_val),
            "missing_value_deals_count": total_deals - len(deals_with_val),
            "total_pipeline_val": total_pipeline_val,
            "formatted_total_pipeline": self.format_currency(total_pipeline_val),
            "weighted_pipeline_val": weighted_pipeline_val,
            "formatted_weighted_pipeline": self.format_currency(weighted_pipeline_val),
            "avg_deal_size": avg_deal_size,
            "formatted_avg_deal_size": self.format_currency(avg_deal_size),
            "win_rate_pct": win_rate,
            "won_deals_count": won_cnt,
            "lost_deals_count": lost_cnt,
            "stages": stage_records,
            "sectors": sector_records,
            "top_deals": top_deals
        }

    # -------------------------------------------------------------------------
    # 2. WORK ORDERS & OPERATIONS ANALYTICS
    # -------------------------------------------------------------------------
    def get_operations_summary(self, sector_filter: Optional[str] = None, owner_filter: Optional[str] = None) -> Dict[str, Any]:
        """Aggregate operational delivery, execution progress, and financial realization."""
        df = self.df_wo.copy()
        if df.empty:
            return {
                "total_work_orders": 0, "total_po_val_excl": 0, "formatted_total_po_excl": "₹0",
                "total_po_val_incl": 0, "formatted_total_po_incl": "₹0",
                "total_billed_excl": 0, "formatted_total_billed_excl": "₹0",
                "total_unbilled_excl": 0, "formatted_total_unbilled_excl": "₹0",
                "total_collected": 0, "formatted_total_collected": "₹0",
                "total_ar": 0, "formatted_total_ar": "₹0",
                "billing_realization_rate_pct": 0, "collection_rate_pct": 0,
                "execution_breakdown": [], "ar_priority_accounts": []
            }

        if sector_filter and sector_filter.lower() != "all":
            df = df[df["sector"].str.lower() == sector_filter.lower()]

        if owner_filter and owner_filter.lower() != "all":
            df = df[df["owner_code"].str.upper() == owner_filter.upper()]

        total_wo = len(df)
        total_po_val_excl = float(df["amount_excl_gst"].sum())
        total_po_val_incl = float(df["amount_incl_gst"].sum())
        total_billed_excl = float(df["billed_excl_gst"].sum())
        total_billed_incl = float(df["billed_incl_gst"].sum())
        total_unbilled_excl = float(df["unbilled_excl_gst"].sum())
        total_collected = float(df["collected_amount"].sum())
        total_ar = float(df["effective_ar"].sum())

        # Execution status breakdown
        exec_records = []
        if not df.empty and "execution_status" in df.columns:
            exec_group = df.groupby("execution_status", observed=False).agg(
                wo_count=("serial_no", "count"),
                po_value=("amount_excl_gst", "sum"),
                unbilled_value=("unbilled_excl_gst", "sum")
            ).reset_index()

            for _, row in exec_group.iterrows():
                exec_records.append({
                    "status": row["execution_status"],
                    "count": int(row["wo_count"]),
                    "po_value": float(row["po_value"]),
                    "formatted_po_value": self.format_currency(row["po_value"]),
                    "unbilled_value": float(row["unbilled_value"]),
                    "formatted_unbilled": self.format_currency(row["unbilled_value"])
                })

        # AR Priority Accounts
        ar_priority_records = []
        if not df.empty:
            ar_priority_df = df[df["is_ar_priority"] | (df["effective_ar"] > 500000)].sort_values(by="effective_ar", ascending=False)
            for _, row in ar_priority_df.head(6).iterrows():
                ar_priority_records.append({
                    "serial_no": row["serial_no"],
                    "customer_code": row["customer_code_raw"],
                    "deal_name": row["deal_name"],
                    "sector": row["sector"],
                    "owner": row["owner_code"],
                    "po_amount": float(row["amount_excl_gst"]),
                    "formatted_po_amount": self.format_currency(row["amount_excl_gst"]),
                    "billed_incl_gst": float(row["billed_incl_gst"]),
                    "formatted_billed": self.format_currency(row["billed_incl_gst"]),
                    "collected": float(row["collected_amount"]),
                    "formatted_collected": self.format_currency(row["collected_amount"]),
                    "outstanding_ar": float(row["effective_ar"]),
                    "formatted_ar": self.format_currency(row["effective_ar"]),
                    "is_priority_flag": bool(row["is_ar_priority"])
                })

        # Billing realization rate
        realization_rate = round((total_billed_excl / total_po_val_excl * 100), 1) if total_po_val_excl > 0 else 0.0
        collection_rate = round((total_collected / total_billed_incl * 100), 1) if total_billed_incl > 0 else 0.0

        return {
            "total_work_orders": total_wo,
            "total_po_val_excl": total_po_val_excl,
            "formatted_total_po_excl": self.format_currency(total_po_val_excl),
            "total_po_val_incl": total_po_val_incl,
            "formatted_total_po_incl": self.format_currency(total_po_val_incl),
            "total_billed_excl": total_billed_excl,
            "formatted_total_billed_excl": self.format_currency(total_billed_excl),
            "total_unbilled_excl": total_unbilled_excl,
            "formatted_total_unbilled_excl": self.format_currency(total_unbilled_excl),
            "total_collected": total_collected,
            "formatted_total_collected": self.format_currency(total_collected),
            "total_ar": total_ar,
            "formatted_total_ar": self.format_currency(total_ar),
            "billing_realization_rate_pct": realization_rate,
            "collection_rate_pct": collection_rate,
            "execution_breakdown": exec_records,
            "ar_priority_accounts": ar_priority_records
        }

    # -------------------------------------------------------------------------
    # 3. CROSS-BOARD INTEGRATION & CLIENT 360
    # -------------------------------------------------------------------------
    def get_cross_board_overview(self, sector_filter: Optional[str] = None) -> Dict[str, Any]:
        """Join Deals and Work Orders to provide full-funnel business intelligence."""
        pipeline = self.get_pipeline_summary(sector_filter=sector_filter)
        ops = self.get_operations_summary(sector_filter=sector_filter)

        deals_clients = set(self.df_deals["normalized_client_code"].dropna().unique()) if not self.df_deals.empty else set()
        wo_clients = set(self.df_wo["normalized_client_code"].dropna().unique()) if not self.df_wo.empty else set()
        overlap_clients = deals_clients.intersection(wo_clients)

        client_summary = []
        for client in sorted(overlap_clients):
            c_deals = self.df_deals[self.df_deals["normalized_client_code"] == client] if not self.df_deals.empty else pd.DataFrame()
            c_wo = self.df_wo[self.df_wo["normalized_client_code"] == client] if not self.df_wo.empty else pd.DataFrame()
            
            p_val = float(c_deals["deal_value"].sum()) if not c_deals.empty else 0.0
            po_val = float(c_wo["amount_excl_gst"].sum()) if not c_wo.empty else 0.0
            billed_val = float(c_wo["billed_excl_gst"].sum()) if not c_wo.empty else 0.0
            unbilled_val = float(c_wo["unbilled_excl_gst"].sum()) if not c_wo.empty else 0.0
            ar_val = float(c_wo["effective_ar"].sum()) if not c_wo.empty else 0.0
            
            sec = "Unspecified"
            if not c_wo.empty and "sector" in c_wo.columns:
                sec = c_wo["sector"].iloc[0]
            elif not c_deals.empty and "sector" in c_deals.columns:
                sec = c_deals["sector"].iloc[0]

            client_summary.append({
                "client_code": client,
                "sector": sec,
                "pipeline_deals_count": len(c_deals),
                "pipeline_value": p_val,
                "formatted_pipeline_value": self.format_currency(p_val),
                "work_orders_count": len(c_wo),
                "po_value": po_val,
                "formatted_po_value": self.format_currency(po_val),
                "billed_value": billed_val,
                "formatted_billed": self.format_currency(billed_val),
                "unbilled_value": unbilled_val,
                "formatted_unbilled": self.format_currency(unbilled_val),
                "ar_balance": ar_val,
                "formatted_ar": self.format_currency(ar_val),
                "active_statuses": list(c_wo["execution_status"].unique()) if not c_wo.empty else []
            })

        client_summary.sort(key=lambda x: x["pipeline_value"] + x["po_value"], reverse=True)

        return {
            "pipeline": pipeline,
            "operations": ops,
            "total_overlapping_clients": len(overlap_clients),
            "top_cross_board_clients": client_summary[:10]
        }

    # -------------------------------------------------------------------------
    # 4. SECTOR 360 BENCHMARK
    # -------------------------------------------------------------------------
    def get_sector_360(self, sector_name: str) -> Dict[str, Any]:
        """Deep-dive into a single sector across both sales pipeline and operations."""
        canonical = normalize_sector(sector_name)
        d_sub = self.df_deals[self.df_deals["sector"].str.lower() == canonical.lower()] if not self.df_deals.empty else pd.DataFrame()
        wo_sub = self.df_wo[self.df_wo["sector"].str.lower() == canonical.lower()] if not self.df_wo.empty else pd.DataFrame()

        pipeline = self.get_pipeline_summary(sector_filter=canonical)
        ops = self.get_operations_summary(sector_filter=canonical)

        p_val = float(d_sub["deal_value"].sum()) if not d_sub.empty else 0.0
        w_val = float(d_sub["weighted_deal_value"].sum()) if not d_sub.empty else 0.0
        po_val = float(wo_sub["amount_excl_gst"].sum()) if not wo_sub.empty else 0.0
        b_val = float(wo_sub["billed_excl_gst"].sum()) if not wo_sub.empty else 0.0
        u_val = float(wo_sub["unbilled_excl_gst"].sum()) if not wo_sub.empty else 0.0
        c_val = float(wo_sub["collected_amount"].sum()) if not wo_sub.empty else 0.0
        ar_val = float(wo_sub["effective_ar"].sum()) if not wo_sub.empty else 0.0

        return {
            "sector": canonical,
            "deal_count": len(d_sub),
            "pipeline_value": p_val,
            "formatted_pipeline_val": self.format_currency(p_val),
            "weighted_pipeline_val": w_val,
            "formatted_weighted_val": self.format_currency(w_val),
            "work_orders_count": len(wo_sub),
            "po_value": po_val,
            "formatted_po_val": self.format_currency(po_val),
            "billed_value": b_val,
            "formatted_billed_val": self.format_currency(b_val),
            "unbilled_value": u_val,
            "formatted_unbilled_val": self.format_currency(u_val),
            "collected_value": c_val,
            "formatted_collected_val": self.format_currency(c_val),
            "ar_value": ar_val,
            "formatted_ar_val": self.format_currency(ar_val),
            "pipeline_details": pipeline,
            "ops_details": ops
        }
