"""
tests/test_bi_engine.py
Unit tests for Business Intelligence calculations, cross-board joins, and KPIs.
"""

import pytest
import pandas as pd
from app.data_cleaner import DataResilienceEngine
from app.bi_engine import BusinessIntelligenceEngine

@pytest.fixture
def sample_engine():
    raw_deals = pd.DataFrame([
        {
            "Deal Name": "Naruto",
            "Owner code": "OWNER_001",
            "Client Code": "COMPANY089",
            "Deal Status": "Open",
            "Close Date (A)": None,
            "Closure Probability": "High",
            "Masked Deal value": 500000.0,
            "Tentative Close Date": "2026-02-26",
            "Deal Stage": "B. Sales Qualified Leads",
            "Sector/service": "Mining",
            "Created Date": "2025-12-26"
        },
        {
            "Deal Name": "Sakura",
            "Owner code": "OWNER_002",
            "Client Code": "COMPANY002",
            "Deal Status": "Won",
            "Close Date (A)": "2025-07-31",
            "Closure Probability": "High",
            "Masked Deal value": 1000000.0,
            "Tentative Close Date": "2025-07-31",
            "Deal Stage": "Closed Won",
            "Sector/service": "Powerline",
            "Created Date": "2025-05-16"
        }
    ])

    raw_wo = pd.DataFrame([
        {
            "Deal name masked": "Sakura",
            "Customer Name Code": "WOCOMPANY_002",
            "Serial #": "SDPLDEAL-002",
            "Nature of Work": "One time Project",
            "Execution Status": "Completed",
            "Date of PO/LOI": "2025-05-16",
            "Sector": "Powerline",
            "Amount in Rupees (Excl of GST) (Masked)": 1000000.0,
            "Amount in Rupees (Incl of GST) (Masked)": 1180000.0,
            "Billed Value in Rupees (Excl of GST.) (Masked)": 800000.0,
            "Billed Value in Rupees (Incl of GST.) (Masked)": 944000.0,
            "Collected Amount in Rupees (Incl of GST.) (Masked)": 500000.0,
            "Amount to be billed in Rs. (Exl. of GST) (Masked)": 200000.0,
            "Amount Receivable (Masked)": 444000.0,
            "AR Priority account": "Priority",
            "BD/KAM Personnel code": "OWNER_002"
        }
    ])

    df_deals, deals_dq = DataResilienceEngine.clean_deals_data(raw_deals)
    df_wo, wo_dq = DataResilienceEngine.clean_work_orders_data(raw_wo)
    return BusinessIntelligenceEngine(df_deals, df_wo, deals_dq, wo_dq)

def test_pipeline_summary(sample_engine):
    summary = sample_engine.get_pipeline_summary()
    assert summary["total_deals"] == 2
    assert summary["total_pipeline_val"] == 1500000.0
    assert summary["weighted_pipeline_val"] == (500000.0 * 0.8) + (1000000.0 * 0.8)
    assert summary["won_deals_count"] == 1

def test_operations_summary(sample_engine):
    summary = sample_engine.get_operations_summary()
    assert summary["total_work_orders"] == 1
    assert summary["total_po_val_excl"] == 1000000.0
    assert summary["total_billed_excl"] == 800000.0
    assert summary["total_unbilled_excl"] == 200000.0
    assert summary["billing_realization_rate_pct"] == 80.0
    assert summary["total_collected"] == 500000.0
    assert len(summary["ar_priority_accounts"]) == 1

def test_cross_board_overview(sample_engine):
    cross = sample_engine.get_cross_board_overview()
    assert cross["total_overlapping_clients"] >= 1
    top_c = cross["top_cross_board_clients"][0]
    assert top_c["client_code"] == "COMPANY002"
    assert top_c["pipeline_value"] == 1000000.0
    assert top_c["po_value"] == 1000000.0

def test_sector_360(sample_engine):
    sec = sample_engine.get_sector_360("Powerline")
    assert sec["sector"] == "Powerline"
    assert sec["deal_count"] == 1
    assert sec["work_orders_count"] == 1
    assert sec["po_value"] == 1000000.0
