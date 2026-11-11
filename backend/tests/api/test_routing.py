import pytest
from app.core.routing import resolve_routing

def test_resolve_routing_historical_named_figure():
    rule = resolve_routing("historical", has_named_historical_figure=True)
    assert rule.narrative_shape_default == "reflective"
    assert rule.fact_check_enabled is True
    assert rule.model_name_default == "gemini-3.1-flash-lite"
    assert rule.reality_binding_level == "strict"

def test_resolve_routing_historical_no_named_figure():
    rule = resolve_routing("historical", has_named_historical_figure=False)
    assert rule.narrative_shape_default == "explanatory"
    assert rule.fact_check_enabled is True
    assert rule.reality_binding_level == "strict"

def test_resolve_routing_scientific():
    rule = resolve_routing("scientific")
    assert rule.narrative_shape_default == "explanatory"
    assert rule.fact_check_enabled is True
    assert rule.reality_binding_level == "strict"

def test_resolve_routing_fictional_mythology():
    rule = resolve_routing("fictional_mythology")
    assert rule.narrative_shape_default == "adventure"
    assert rule.fact_check_enabled is False
    assert rule.reality_binding_level == "soft"

def test_resolve_routing_fictional_original():
    rule = resolve_routing("fictional_original")
    assert rule.narrative_shape_default == "adventure"
    assert rule.fact_check_enabled is False
    assert rule.reality_binding_level == "soft"

def test_resolve_routing_unknown_fallback():
    rule = resolve_routing("non_existent_topic_type")
    # Should fallback to fictional_original
    assert rule.narrative_shape_default == "adventure"
    assert rule.fact_check_enabled is False
    assert rule.reality_binding_level == "soft"
