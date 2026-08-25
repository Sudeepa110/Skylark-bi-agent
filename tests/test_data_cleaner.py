"""
tests/test_data_cleaner.py
Unit tests for data resilience, date parsing, string normalization, and DQ auditing.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from app.data_cleaner import (
    parse_date_resilient,
    normalize_sector,
    normalize_deal_stage,
    extract_numeric,
    normalize_client_code,
    DataResilienceEngine
)

def test_parse_date_resilient():
    # ISO strings
    assert parse_date_resilient("2025-10-29").year == 2025
    assert parse_date_resilient("2025-10-29").month == 10
    
    # Datetime objects
    dt = datetime(2025, 7, 31)
    assert parse_date_resilient(dt).day == 31
    
    # Pandas Timestamp
    ts = pd.Timestamp("2025-12-26")
    assert parse_date_resilient(ts).month == 12
    
    # Nulls & edge cases
    assert parse_date_resilient(None) is None
    assert parse_date_resilient("nan") is None
    assert parse_date_resilient("NaT") is None
    assert parse_date_resilient("-") is None
    assert parse_date_resilient("") is None

def test_normalize_sector():
    assert normalize_sector("mining") == "Mining"
    assert normalize_sector("POWERLINE") == "Powerline"
    assert normalize_sector("power line") == "Powerline"
    assert normalize_sector("renewables") == "Renewables"
    assert normalize_sector("Solar") == "Renewables"
    assert normalize_sector("Tender") == "Tender"
    assert normalize_sector(None) == "Unspecified"
    assert normalize_sector("nan") == "Unspecified"

def test_normalize_deal_stage():
    name, cat = normalize_deal_stage("B. Sales Qualified Leads")
    assert name == "Sales Qualified Leads"
    assert cat == "Qualified"

    name, cat = normalize_deal_stage("E. Proposal/Commercials Sent")
    assert cat == "Proposal Sent"

    name, cat = normalize_deal_stage("Closed Won")
    assert cat == "Won"

    name, cat = normalize_deal_stage("Lost to competitor")
    assert cat == "Lost"

def test_extract_numeric():
    assert extract_numeric(489360.0) == 489360.0
    assert extract_numeric("489360") == 489360.0
    assert extract_numeric("₹ 1,54,150.00") == 154150.0
    assert extract_numeric("5360 HA") == 5360.0
    assert extract_numeric("4") == 4.0
    assert extract_numeric(None) == 0.0
    assert extract_numeric(np.nan) == 0.0

def test_normalize_client_code():
    assert normalize_client_code("WOCOMPANY_002") == "COMPANY002"
    assert normalize_client_code("COMPANY002") == "COMPANY002"
    assert normalize_client_code("WOCOMPANY_038") == "COMPANY038"
    assert normalize_client_code("company_124") == "COMPANY124"
    assert normalize_client_code(None) == "UNKNOWN_CLIENT"

def test_clean_deals_data():
    raw_deals = pd.DataFrame([
        {
            "Deal Name": "Naruto",
            "Owner code": "OWNER_001",
            "Client Code": "COMPANY089",
            "Deal Status": "Open",
            "Close Date (A)": None,
            "Closure Probability": "High",
            "Masked Deal value": "489360",
            "Tentative Close Date": "2026-02-26",
            "Deal Stage": "B. Sales Qualified Leads",
            "Sector/service": "mining",
            "Created Date": "2025-12-26"
        },
        {
            "Deal Name": "Sasuke",
            "Owner code": "OWNER_002",
            "Client Code": "COMPANY091",
            "Deal Status": "Open",
            "Close Date (A)": None,
            "Closure Probability": "Low",
            "Masked Deal value": 0,
            "Tentative Close Date": None,
            "Deal Stage": "E. Proposal/Commercials Sent",
            "Sector/service": "powerline",
            "Created Date": "2025-11-12"
        }
    ])

    df_cleaned, dq = DataResilienceEngine.clean_deals_data(raw_deals)
    assert len(df_cleaned) == 2
    assert df_cleaned["sector"].iloc[0] == "Mining"
    assert df_cleaned["probability_pct"].iloc[0] == 0.80
    assert df_cleaned["weighted_deal_value"].iloc[0] == 489360.0 * 0.80
    assert dq["total_deals"] == 2
    assert dq["missing_value_count"] == 1
