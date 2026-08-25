"""
app/data_cleaner.py
Resilient Data Normalization and Data Quality Audit Engine.
Cleans messy real-world data from Monday.com boards:
- Date normalization & fiscal calendar extraction
- Sector, stage, casing, and string standardization
- Numeric parsing & currency extraction
- Cross-board key harmonization (Client Code <-> Customer Name Code)
- Automated Data Quality Auditing with explicit caveat generation
"""

import re
import numpy as np
import pandas as pd
from datetime import datetime
from dateutil import parser as date_parser
from typing import Dict, Any, List, Optional, Tuple

SECTOR_CANONICAL_MAP = {
    "mining": "Mining",
    "powerline": "Powerline",
    "power line": "Powerline",
    "renewables": "Renewables",
    "renewable": "Renewables",
    "solar": "Renewables",
    "wind": "Renewables",
    "tender": "Tender",
    "tenders": "Tender",
    "aerospace": "Aerospace/Defence",
    "defence": "Aerospace/Defence",
    "defense": "Aerospace/Defence",
    "security": "Aerospace/Defence",
    "telecom": "Telecom",
    "highway": "Highways/Infra",
    "highways": "Highways/Infra",
    "infra": "Highways/Infra",
    "infrastructure": "Highways/Infra",
    "railways": "Railways",
    "forestry": "Forestry/Agri",
    "agriculture": "Forestry/Agri",
    "enterprise": "Enterprise",
}

PROBABILITY_WEIGHTS = {
    "high": 0.80,
    "medium": 0.50,
    "low": 0.20,
}

def parse_date_resilient(val: Any) -> Optional[pd.Timestamp]:
    """Parse various date formats gracefully, returning pd.Timestamp or None."""
    if val is None:
        return None
    if isinstance(val, (pd.Series, list, np.ndarray)):
        if len(val) == 0:
            return None
        val = val.iloc[0] if isinstance(val, pd.Series) else val[0]
    try:
        if pd.isna(val):
            return None
    except Exception:
        pass
    if isinstance(val, (pd.Timestamp, datetime)):
        return pd.to_datetime(val)
    val_str = str(val).strip()
    if not val_str or val_str.lower() in ("nan", "nat", "none", "null", "-", "na", "n/a"):
        return None
    try:
        dt = date_parser.parse(val_str, fuzzy=True)
        return pd.to_datetime(dt)
    except Exception:
        return None

def normalize_sector(val: Any) -> str:
    """Standardize sector names and handle casing/aliases."""
    if val is None:
        return "Unspecified"
    if isinstance(val, (pd.Series, list, np.ndarray)):
        if len(val) == 0:
            return "Unspecified"
        val = val.iloc[0] if isinstance(val, pd.Series) else val[0]
    try:
        if pd.isna(val):
            return "Unspecified"
    except Exception:
        pass
    val_str = str(val).strip()
    if not val_str or val_str.lower() in ("nan", "none", "null", "-"):
        return "Unspecified"
    
    val_lower = val_str.lower()
    for key, canonical in SECTOR_CANONICAL_MAP.items():
        if key in val_lower:
            return canonical
    return val_str.title()

def normalize_deal_stage(val: Any) -> Tuple[str, str]:
    """Return (clean_stage_name, stage_category)."""
    if val is None:
        return ("Unassigned", "Lead")
    if isinstance(val, (pd.Series, list, np.ndarray)):
        if len(val) == 0:
            return ("Unassigned", "Lead")
        val = val.iloc[0] if isinstance(val, pd.Series) else val[0]
    try:
        if pd.isna(val):
            return ("Unassigned", "Lead")
    except Exception:
        pass
    val_str = str(val).strip()
    # Strip prefix like "B. ", "1. ", "D. "
    clean_name = re.sub(r"^[A-Za-z0-9]\.\s*", "", val_str).strip()
    clean_lower = clean_name.lower()
    
    if "won" in clean_lower:
        category = "Won"
    elif "lost" in clean_lower or "drop" in clean_lower:
        category = "Lost"
    elif "proposal" in clean_lower or "commercial" in clean_lower:
        category = "Proposal Sent"
    elif "feasibility" in clean_lower:
        category = "Feasibility"
    elif "negotiation" in clean_lower:
        category = "Negotiation"
    elif "hold" in clean_lower:
        category = "On Hold"
    elif "qualified" in clean_lower:
        category = "Qualified"
    elif "nurture" in clean_lower:
        category = "Nurture"
    else:
        category = "Lead"
        
    return clean_name, category

def extract_numeric(val: Any) -> float:
    """Extract float from number or string like '5360 HA' or '₹ 154,150.00'."""
    if val is None:
        return 0.0
    if isinstance(val, (pd.Series, list, np.ndarray)):
        if len(val) == 0:
            return 0.0
        val = val.iloc[0] if isinstance(val, pd.Series) else val[0]
    try:
        if pd.isna(val):
            return 0.0
    except Exception:
        pass
    if isinstance(val, (int, float)):
        return float(val) if not np.isnan(val) else 0.0
    val_str = str(val).strip().replace(",", "").replace("₹", "").replace("$", "")
    match = re.search(r"[-+]?\d*\.?\d+", val_str)
    if match:
        try:
            return float(match.group())
        except ValueError:
            return 0.0
    return 0.0

def normalize_client_code(val: Any) -> str:
    """Harmonize client codes between Deals (COMPANY089) and Work Orders (WOCOMPANY_089)."""
    if val is None:
        return "UNKNOWN_CLIENT"
    if isinstance(val, (pd.Series, list, np.ndarray)):
        if len(val) == 0:
            return "UNKNOWN_CLIENT"
        val = val.iloc[0] if isinstance(val, pd.Series) else val[0]
    try:
        if pd.isna(val):
            return "UNKNOWN_CLIENT"
    except Exception:
        pass
    code = str(val).strip().upper().replace("_", "").replace("-", "").replace(" ", "")
    if code.startswith("WOCOMPANY"):
        code = "COMPANY" + code[9:]
    return code

class DataResilienceEngine:
    """Main data cleaning and resilience pipeline for Monday.com boards."""

    @staticmethod
    def clean_deals_data(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Clean and normalize the Deals DataFrame."""
        if df.empty:
            return df, {}

        df = df.copy()
        
        # 1. Column standardization
        col_rename = {}
        for col in df.columns:
            c_low = col.lower().strip()
            if "deal name" in c_low or col == "name":
                col_rename[col] = "deal_name"
            elif "owner" in c_low:
                col_rename[col] = "owner_code"
            elif "client" in c_low or "customer" in c_low:
                col_rename[col] = "client_code"
            elif "deal status" in c_low or c_low == "status":
                col_rename[col] = "deal_status"
            elif "close date" in c_low and "(a)" in c_low:
                col_rename[col] = "actual_close_date"
            elif "tentative" in c_low or "expected close" in c_low:
                col_rename[col] = "tentative_close_date"
            elif "probability" in c_low:
                col_rename[col] = "closure_probability"
            elif "value" in c_low or "amount" in c_low:
                col_rename[col] = "deal_value"
            elif "stage" in c_low:
                col_rename[col] = "deal_stage"
            elif "product" in c_low:
                col_rename[col] = "product_deal"
            elif "sector" in c_low or "service" in c_low:
                col_rename[col] = "sector"
            elif "created" in c_low:
                col_rename[col] = "created_date"
        
        df = df.rename(columns=col_rename)
        df = df.loc[:, ~df.columns.duplicated(keep="first")]

        # 2. String & categorical cleanup
        def get_series(col_name, default_val):
            if col_name in df.columns:
                s = df[col_name]
                if isinstance(s, pd.DataFrame):
                    s = s.iloc[:, 0]
                return s
            return pd.Series([default_val] * len(df))

        df["deal_name"] = get_series("deal_name", "Unknown Deal").fillna("Unknown Deal").astype(str).str.strip()
        df["owner_code"] = get_series("owner_code", "Unassigned").fillna("Unassigned").astype(str).str.strip().str.upper()
        df["client_code_raw"] = get_series("client_code", "UNKNOWN").fillna("UNKNOWN").astype(str).str.strip()
        df["normalized_client_code"] = df["client_code_raw"].apply(normalize_client_code)
        df["sector"] = get_series("sector", "Unspecified").apply(normalize_sector)
        df["product_deal"] = get_series("product_deal", "Standard Service").fillna("Standard Service").astype(str).str.strip()
        
        # 3. Stages & Probabilities
        raw_stage = get_series("deal_stage", "Qualified")
        stage_info = raw_stage.apply(normalize_deal_stage)
        df["clean_deal_stage"] = [s[0] for s in stage_info]
        df["stage_category"] = [s[1] for s in stage_info]
        
        def parse_prob(prob_val):
            if prob_val is None:
                return 0.30
            try:
                if pd.isna(prob_val):
                    return 0.30
            except Exception:
                pass
            p_str = str(prob_val).lower().strip()
            if not p_str or p_str in ("nan", "none", "null"):
                return 0.30
            for k, weight in PROBABILITY_WEIGHTS.items():
                if k in p_str:
                    return weight
            try:
                num = float(p_str.replace("%", ""))
                return num / 100.0 if num > 1.0 else num
            except:
                return 0.30

        df["probability_pct"] = get_series("closure_probability", None).apply(parse_prob)

        # 4. Dates
        df["created_dt"] = get_series("created_date", None).apply(parse_date_resilient)
        df["actual_close_dt"] = get_series("actual_close_date", None).apply(parse_date_resilient)
        df["tentative_close_dt"] = get_series("tentative_close_date", None).apply(parse_date_resilient)
        df["effective_close_dt"] = df["actual_close_dt"].fillna(df["tentative_close_dt"])
        
        # Extract Quarter & Year
        df["close_quarter"] = df["effective_close_dt"].apply(lambda d: f"Q{d.quarter} {d.year}" if pd.notna(d) else "No Date")
        df["close_year"] = df["effective_close_dt"].apply(lambda d: d.year if pd.notna(d) else None)
        df["is_closed"] = df["actual_close_dt"].notna() | df["stage_category"].isin(["Won", "Lost"])

        # 5. Deal Values
        df["deal_value"] = get_series("deal_value", 0.0).apply(extract_numeric)
        df["weighted_deal_value"] = df["deal_value"] * df["probability_pct"]

        # Data quality metrics for Deals
        dq_stats = {
            "total_deals": len(df),
            "missing_value_count": int((df["deal_value"] == 0).sum()),
            "missing_value_pct": round(float((df["deal_value"] == 0).sum() / len(df) * 100), 1) if len(df) > 0 else 0.0,
            "missing_close_date_count": int(df["effective_close_dt"].isna().sum()),
            "missing_actual_close_date_count": int(df["actual_close_dt"].isna().sum()),
            "missing_owner_count": int((df["owner_code"].isin(["UNASSIGNED", "NAN", "NONE", ""])).sum()),
            "missing_sector_count": int((df["sector"] == "Unspecified").sum()),
        }

        return df, dq_stats

    @staticmethod
    def clean_work_orders_data(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Clean and normalize the Work Orders DataFrame."""
        if df.empty:
            return df, {}

        df = df.copy()

        # Map column titles
        col_rename = {}
        for col in df.columns:
            c_low = col.lower().strip()
            if "deal name" in c_low:
                col_rename[col] = "deal_name"
            elif "customer" in c_low or "client" in c_low:
                col_rename[col] = "customer_code"
            elif "serial" in c_low or col == "name":
                col_rename[col] = "serial_no"
            elif "nature of work" in c_low:
                col_rename[col] = "nature_of_work"
            elif "execution status" in c_low:
                col_rename[col] = "execution_status"
            elif "delivery date" in c_low:
                col_rename[col] = "data_delivery_date"
            elif "date of po" in c_low or "loi" in c_low:
                col_rename[col] = "date_of_po"
            elif "probable start" in c_low:
                col_rename[col] = "start_date"
            elif "probable end" in c_low:
                col_rename[col] = "end_date"
            elif "bd/kam" in c_low or "personnel" in c_low:
                col_rename[col] = "owner_code"
            elif "sector" in c_low:
                col_rename[col] = "sector"
            elif "type of work" in c_low:
                col_rename[col] = "type_of_work"
            elif "platform" in c_low or "spectra" in c_low:
                col_rename[col] = "software_platform"
            elif "last invoice date" in c_low:
                col_rename[col] = "last_invoice_date"
            elif "invoice no" in c_low:
                col_rename[col] = "invoice_no"
            elif "collected" in c_low:
                col_rename[col] = "collected_amount"
            elif "amount to be billed" in c_low or "unbilled" in c_low:
                if "incl" in c_low:
                    col_rename[col] = "unbilled_incl_gst"
                else:
                    col_rename[col] = "unbilled_excl_gst"
            elif "billed" in c_low:
                if "incl" in c_low:
                    col_rename[col] = "billed_incl_gst"
                else:
                    col_rename[col] = "billed_excl_gst"
            elif "receivable" in c_low:
                col_rename[col] = "amount_receivable"
            elif "amount in rupees (excl" in c_low or "amount excl" in c_low:
                col_rename[col] = "amount_excl_gst"
            elif "amount in rupees (incl" in c_low or "amount incl" in c_low:
                col_rename[col] = "amount_incl_gst"
            elif "priority" in c_low:
                col_rename[col] = "ar_priority"
            elif "quantity by ops" in c_low:
                col_rename[col] = "ops_quantity"
            elif "quantities as per po" in c_low:
                col_rename[col] = "po_quantity_raw"
            elif "quantity billed" in c_low:
                col_rename[col] = "billed_quantity"
            elif "balance in quantity" in c_low:
                col_rename[col] = "balance_quantity"
            elif "invoice status" in c_low:
                col_rename[col] = "invoice_status"
            elif "billing status" in c_low:
                col_rename[col] = "billing_status"

        df = df.rename(columns=col_rename)
        df = df.loc[:, ~df.columns.duplicated(keep="first")]

        def get_series(col_name, default_val):
            if col_name in df.columns:
                s = df[col_name]
                if isinstance(s, pd.DataFrame):
                    s = s.iloc[:, 0]
                return s
            return pd.Series([default_val] * len(df))

        # Clean strings & codes
        df["serial_no"] = get_series("serial_no", "WO_UNKNOWN").fillna("WO_UNKNOWN").astype(str).str.strip()
        df["deal_name"] = get_series("deal_name", "").fillna("").astype(str).str.strip()
        df["customer_code_raw"] = get_series("customer_code", "UNKNOWN").fillna("UNKNOWN").astype(str).str.strip()
        df["normalized_client_code"] = df["customer_code_raw"].apply(normalize_client_code)
        df["sector"] = get_series("sector", "Unspecified").apply(normalize_sector)
        df["owner_code"] = get_series("owner_code", "Unassigned").fillna("Unassigned").astype(str).str.strip().str.upper()
        df["nature_of_work"] = get_series("nature_of_work", "One time Project").fillna("One time Project").astype(str).str.strip()
        
        # Execution Status
        def clean_exec_status(val):
            if val is None:
                return "Not Specified"
            try:
                if pd.isna(val):
                    return "Not Specified"
            except Exception:
                pass
            s = str(val).strip()
            if not s or s.lower() in ("nan", "none", "null"):
                return "Not Specified"
            s_low = s.lower()
            if "completed" in s_low:
                return "Completed"
            elif "not started" in s_low:
                return "Not Started"
            elif "executed until" in s_low or "in progress" in s_low or "ongoing" in s_low:
                return "In Progress"
            elif "cancelled" in s_low:
                return "Cancelled"
            return s.title()

        df["execution_status"] = get_series("execution_status", None).apply(clean_exec_status)

        # Dates
        df["po_dt"] = get_series("date_of_po", None).apply(parse_date_resilient)
        df["start_dt"] = get_series("start_date", None).apply(parse_date_resilient)
        df["end_dt"] = get_series("end_date", None).apply(parse_date_resilient)
        df["delivery_dt"] = get_series("data_delivery_date", None).apply(parse_date_resilient)
        df["last_invoice_dt"] = get_series("last_invoice_date", None).apply(parse_date_resilient)
        
        # Quarter & Year from PO Date
        df["po_quarter"] = df["po_dt"].apply(lambda d: f"Q{d.quarter} {d.year}" if pd.notna(d) else "No Date")
        df["po_year"] = df["po_dt"].apply(lambda d: d.year if pd.notna(d) else None)

        # Numerics & Financials
        for amt_col in [
            "amount_excl_gst", "amount_incl_gst", "billed_excl_gst", "billed_incl_gst",
            "collected_amount", "unbilled_excl_gst", "unbilled_incl_gst", "amount_receivable",
            "ops_quantity", "billed_quantity", "balance_quantity"
        ]:
            df[amt_col] = get_series(amt_col, 0.0).apply(extract_numeric)

        # If unbilled not explicitly present, calculate it
        if "unbilled_excl_gst" not in df.columns or df["unbilled_excl_gst"].sum() == 0:
            df["unbilled_excl_gst"] = (df["amount_excl_gst"] - df["billed_excl_gst"]).clip(lower=0.0)

        # If receivable is missing, compute billed_incl_gst - collected_amount
        calculated_ar = (df["billed_incl_gst"] - df["collected_amount"]).clip(lower=0.0)
        df["effective_ar"] = df["amount_receivable"].replace(0.0, np.nan).fillna(calculated_ar)

        df["is_ar_priority"] = get_series("ar_priority", "").astype(str).str.lower().str.contains("priority")

        # Data quality metrics for Work Orders
        dq_stats = {
            "total_work_orders": len(df),
            "missing_exec_status_count": int((df["execution_status"] == "Not Specified").sum()),
            "missing_po_date_count": int(df["po_dt"].isna().sum()),
            "completed_unbilled_count": int(((df["execution_status"] == "Completed") & (df["billed_excl_gst"] == 0)).sum()),
            "ar_priority_count": int(df["is_ar_priority"].sum()),
            "total_po_value_excl_gst": float(df["amount_excl_gst"].sum()),
            "total_billed_excl_gst": float(df["billed_excl_gst"].sum()),
            "total_unbilled_excl_gst": float(df["unbilled_excl_gst"].sum()),
            "total_collected": float(df["collected_amount"].sum()),
            "total_ar": float(df["effective_ar"].sum())
        }

        return df, dq_stats

    @staticmethod
    def generate_dq_caveats(deals_dq: Dict[str, Any], wo_dq: Dict[str, Any], query_context: Optional[str] = None) -> List[str]:
        """Generate human-readable data quality caveats tailored to query context."""
        caveats = []

        if deals_dq:
            if deals_dq.get("missing_value_count", 0) > 0:
                missing_val_cnt = deals_dq["missing_value_count"]
                total = deals_dq["total_deals"]
                pct = deals_dq.get("missing_value_pct", round(missing_val_cnt / total * 100, 1))
                caveats.append(
                    f"⚠️ **Deal Value Gap**: {missing_val_cnt} of {total} deals ({pct}%) have no masked value recorded ($0/unspecified). Aggregate pipeline figures only sum deals with explicit values."
                )

            if deals_dq.get("missing_actual_close_date_count", 0) > 0:
                missing_cd = deals_dq["missing_actual_close_date_count"]
                total = deals_dq["total_deals"]
                caveats.append(
                    f"⚠️ **Close Date Quality**: {missing_cd} of {total} deals lack an actual close date. Projections and quarter assignments utilize tentative dates where available."
                )

        if wo_dq:
            completed_unbilled = wo_dq.get("completed_unbilled_count", 0)
            if completed_unbilled > 0:
                caveats.append(
                    f"⚠️ **Billing Lag Alert**: {completed_unbilled} work orders are marked as 'Completed' by ops but still have ₹0 billed to date."
                )

            if wo_dq.get("missing_exec_status_count", 0) > 0:
                cnt = wo_dq["missing_exec_status_count"]
                caveats.append(
                    f"⚠️ **Ops Tracking**: {cnt} work orders have missing or unrecorded execution statuses."
                )

        return caveats

DataCleaner = DataResilienceEngine
data_cleaner = DataResilienceEngine()
