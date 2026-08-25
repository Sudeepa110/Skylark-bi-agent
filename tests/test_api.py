"""
tests/test_api.py
Integration tests for FastAPI endpoints (/api/health, /api/boards, /api/chat, /api/leadership-update).
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import pandas as pd

from app.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/health")
    # Health endpoint returns 200 or 503 depending on network
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data

def test_chat_empty_query():
    response = client.post("/api/chat", json={"message": "   "})
    assert response.status_code == 400

def test_chat_ambiguous_query():
    response = client.post("/api/chat", json={"message": "How is performance looking?"})
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "clarification"
    assert len(data["suggested_options"]) > 0

def test_index_html_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Skylark" in response.text
