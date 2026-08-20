from datetime import datetime, timezone
from uuid import uuid4

import pytest

from contract_review.engine.parser.service import ContractParse, ExtractedField, FieldEvidence, FieldStatus, ParseStatus
from contract_review.engine.rules.engine import (
    RestrictedRuleEngine,
    RuleDefinition,
    RuleExpressionError,
    RuleHitResult,
    RuleStatus,
    party_completeness_rule,
)


def parsed_with_party_b(status: FieldStatus) -> ContractParse:
    evidence = None if status is FieldStatus.MISSING else FieldEvidence(2, "乙方：乙公司", 0.42 if status is FieldStatus.LOW_CONFIDENCE else 0.95)
    field = ExtractedField(None if status is FieldStatus.MISSING else "乙公司", status, evidence.confidence if evidence else 0.0, evidence)
    return ContractParse(
        id=uuid4(), attachment_id=uuid4(), parser_version="slice3-v1", status=ParseStatus.SUCCEEDED,
        quality_score=90.0, extracted_payload={"party_b": field}, error_code=None, error_message=None,
        started_at=datetime.now(timezone.utc), finished_at=datetime.now(timezone.utc),
    )


def test_missing_party_hits_high_risk_with_document_scope_evidence():
    hits = RestrictedRuleEngine().run(parsed_with_party_b(FieldStatus.MISSING), [party_completeness_rule()], "req-rule")

    assert len(hits) == 1
    assert hits[0].result is RuleHitResult.HIT
    assert hits[0].severity == "high"
    assert hits[0].evidence.page_no == 0
    assert "未发现字段" in hits[0].evidence.snippet
    assert hits[0].suggested_action == "补充乙方主体信息后重新提交"


def test_low_confidence_party_is_insufficient_evidence_not_a_hit():
    hits = RestrictedRuleEngine().run(parsed_with_party_b(FieldStatus.LOW_CONFIDENCE), [party_completeness_rule()])

    assert hits[0].result is RuleHitResult.INSUFFICIENT_EVIDENCE
    assert hits[0].evidence.page_no == 2
    assert hits[0].suggested_action == "人工补录并重新解析"


def test_present_party_is_not_hit():
    hits = RestrictedRuleEngine().run(parsed_with_party_b(FieldStatus.FOUND), [party_completeness_rule()])

    assert hits[0].result is RuleHitResult.NOT_HIT
    assert hits[0].evidence.page_no == 2
    assert hits[0].suggested_action is None


def test_unpublished_rule_is_not_executed():
    rule = party_completeness_rule()
    draft = RuleDefinition(**{**rule.__dict__, "status": RuleStatus.DRAFT})

    assert RestrictedRuleEngine().run(parsed_with_party_b(FieldStatus.MISSING), [draft]) == []


def test_restricted_dsl_rejects_arbitrary_expression():
    rule = party_completeness_rule()
    unsafe = RuleDefinition(**{**rule.__dict__, "expression": {"op": "python", "code": "__import__('os').system('x')"}})

    with pytest.raises(RuleExpressionError):
        RestrictedRuleEngine().run(parsed_with_party_b(FieldStatus.MISSING), [unsafe])
