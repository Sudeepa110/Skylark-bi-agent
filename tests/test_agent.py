"""
tests/test_agent.py
Unit tests for intent parsing, ambiguity detection, and leadership update generation.
"""

import pytest
from app.agent import ConversationalBIAgent

@pytest.fixture
def test_agent():
    return ConversationalBIAgent()

def test_ambiguity_detection(test_agent):
    # Vague queries should trigger clarification
    ambig1 = test_agent.check_ambiguity("How is performance looking?")
    assert ambig1 is not None
    assert ambig1["is_ambiguous"] is True
    assert len(ambig1["suggested_options"]) >= 2

    ambig2 = test_agent.check_ambiguity("give me an update")
    assert ambig2 is not None
    assert ambig2["is_ambiguous"] is True

    # Specific queries should NOT trigger ambiguity
    not_ambig = test_agent.check_ambiguity("How's our pipeline looking for energy sector this quarter?")
    assert not_ambig is None

def test_intent_classification(test_agent):
    # Leadership update
    assert test_agent.classify_intent("prepare this week's leadership update")["intent"] == "leadership_update"
    assert test_agent.classify_intent("generate executive briefing")["intent"] == "leadership_update"

    # Pipeline
    p_intent = test_agent.classify_intent("How is our sales pipeline looking for mining?")
    assert p_intent["intent"] == "pipeline"
    assert p_intent["sector"] == "Mining"

    # Operations & billing
    o_intent = test_agent.classify_intent("What is our total billed revenue vs unbilled backlog?")
    assert o_intent["intent"] == "operations"

    # Cross board
    c_intent = test_agent.classify_intent("Show cross-board top clients by revenue")
    assert c_intent["intent"] == "cross_board"

    # Data quality
    dq_intent = test_agent.classify_intent("Show data quality audit and missing values")
    assert dq_intent["intent"] == "data_quality"
