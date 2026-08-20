from contract_review.mappers import rule_to_domain, rule_to_orm
from contract_review.rules import (
    RULE_ID_PARTY_001,
    RuleStatus,
    party_completeness_rule,
)


def test_default_rules_have_stable_ids():
    assert party_completeness_rule().id == RULE_ID_PARTY_001
    assert party_completeness_rule().id == party_completeness_rule().id


def test_rule_mapper_roundtrip():
    rule = party_completeness_rule()
    back = rule_to_domain(rule_to_orm(rule))
    assert back.id == rule.id
    assert back.rule_code == "RULE-PARTY-001"
    assert back.name == "乙方主体完整性"
    assert back.status is RuleStatus.PUBLISHED
    assert back.expression == {"op": "field_status", "field": "party_b", "equals": "missing"}
    assert back.contract_types == ("after_sales", "sales")
    assert back.severity == "high"
