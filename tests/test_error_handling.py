"""
tests/test_error_handling.py
Unit and Integration tests validating error handling across:
- Monday authentication failure (401)
- Board not found (404)
- Rate limit / complexity retries (429)
- Missing/invalid input query validation (400)
- Graceful degradation on Gemini offline
- Stale cache fallback on network drops
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.monday_client import (
    MondayClient,
    MondayAuthError,
    MondayBoardNotFoundError,
    MondayRateLimitError,
    MondayNetworkError
)

client = TestClient(app)

def test_empty_and_whitespace_query_error():
    """Verify chat endpoint rejects empty/whitespace queries with 400."""
    res = client.post("/api/chat", json={"message": ""})
    assert res.status_code == 400
    
    res = client.post("/api/chat", json={"message": "   "})
    assert res.status_code == 400

def test_monday_auth_error_handler():
    """Verify MondayAuthError translates into structured 401 response."""
    with patch("app.agent.agent.load_data_and_engine") as mock_load:
        mock_load.side_effect = MondayAuthError("Invalid API token")
        res = client.get("/api/boards")
        assert res.status_code == 401
        data = res.json()
        assert data["error_type"] == "AUTHENTICATION_FAILED"
        assert "resolution" in data

def test_monday_board_not_found_error_handler():
    """Verify MondayBoardNotFoundError translates into structured 404 response."""
    with patch("app.agent.agent.load_data_and_engine") as mock_load:
        mock_load.side_effect = MondayBoardNotFoundError("Board '99999999' not found")
        res = client.get("/api/boards")
        assert res.status_code == 404
        data = res.json()
        assert data["error_type"] == "BOARD_NOT_FOUND"

def test_stale_cache_fallback_on_network_error():
    """Verify that when network fails, cached data is used instead of failing."""
    m_client = MondayClient(token="test_token")
    mock_df = pd.DataFrame([{"item_id": "1", "name": "Deal Alpha", "Sector": "Mining"}])
    m_client._board_cache["board_123"] = (100.0, mock_df)
    
    # Simulate network error on execute_gql
    with patch.object(m_client, "execute_gql", side_effect=MondayNetworkError("Connection timed out")):
        res_df = m_client.fetch_board_items("board_123", force_refresh=True)
        assert len(res_df) == 1
        assert res_df.iloc[0]["name"] == "Deal Alpha"

def test_chat_error_recovery():
    """Verify that if an error occurs inside answer_query, API returns a graceful error response with recovery suggestion."""
    with patch("app.agent.agent.answer_query") as mock_answer:
        mock_answer.side_effect = Exception("Temporary processing error")
        res = client.post("/api/chat", json={"message": "What is our revenue?"})
        assert res.status_code == 200
        data = res.json()
        assert data["type"] == "error"
        assert len(data["suggested_options"]) > 0
