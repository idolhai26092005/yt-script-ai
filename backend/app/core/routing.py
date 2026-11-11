from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class RoutingRule:
    narrative_shape_default: str
    fact_check_enabled: bool
    reality_binding_level: str = "soft"
    model_name_default: str = "gemini-3.1-flash-lite"
    custom_system_instruction: Optional[str] = None

ROUTING_TABLE: dict[tuple[str, Optional[str]], RoutingRule] = {
    ("historical", "named_figure"): RoutingRule(
        narrative_shape_default="reflective",
        fact_check_enabled=True,
        reality_binding_level="strict",
    ),
    ("historical", None): RoutingRule(
        narrative_shape_default="explanatory",
        fact_check_enabled=True,
        reality_binding_level="strict",
    ),
    ("scientific", None): RoutingRule(
        narrative_shape_default="explanatory",
        fact_check_enabled=True,
        reality_binding_level="strict",
    ),
    ("fictional_mythology", None): RoutingRule(
        narrative_shape_default="adventure",
        fact_check_enabled=False,
        reality_binding_level="soft",
    ),
    ("fictional_original", None): RoutingRule(
        narrative_shape_default="adventure",
        fact_check_enabled=False,
        reality_binding_level="soft",
    ),
}

def resolve_routing(topic_type: str, has_named_historical_figure: bool = False) -> RoutingRule:
    if topic_type == "historical" and has_named_historical_figure:
        key = ("historical", "named_figure")
    else:
        key = (topic_type, None)
    
    return ROUTING_TABLE.get(key, ROUTING_TABLE[("fictional_original", None)])
