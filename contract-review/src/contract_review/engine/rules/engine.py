from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from contract_review.domain import TaskLog
from contract_review.parser import ContractParse, ExtractedField, FieldEvidence, FieldStatus

# 稳定规则 ID：让 review_rules 种子幂等、rule_hits.rule_id 可追溯。
RULE_ID_PARTY_001 = UUID("a1b2c3d4-0000-4000-8000-000000000001")
RULE_ID_PARTY_002 = UUID("a1b2c3d4-0000-4000-8000-000000000002")
RULE_ID_WARRANTY_001 = UUID("a1b2c3d4-0000-4000-8000-000000000003")


class RuleStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    RETIRED = "retired"


class RuleHitResult(StrEnum):
    HIT = "hit"
    NOT_HIT = "not_hit"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True)
class RuleDefinition:
    id: UUID
    rule_code: str
    version: str
    name: str
    contract_types: tuple[str, ...]
    severity: str
    expression: dict[str, str]
    source_ref: str
    status: RuleStatus


@dataclass(frozen=True)
class RuleHit:
    id: UUID
    parse_id: UUID
    rule_id: UUID
    result: RuleHitResult
    severity: str
    message: str
    evidence: FieldEvidence | None
    suggested_action: str | None
    created_at: datetime


class RuleExpressionError(ValueError):
    pass


class RestrictedRuleEngine:
    """只解释固定 JSON DSL，规则内容永远不会作为代码执行。"""

    ALLOWED_OPERATIONS = {"field_status"}
    ALLOWED_STATUSES = {item.value for item in FieldStatus}

    def run(self, parsed: ContractParse, rules: list[RuleDefinition], request_id: str = "req_local") -> list[RuleHit]:
        hits = []
        for rule in rules:
            if rule.status is not RuleStatus.PUBLISHED:
                continue
            self._validate(rule)
            field = parsed.extracted_payload.get(rule.expression["field"])
            hits.append(self._evaluate(parsed, rule, field))
        return hits

    def _evaluate(self, parsed: ContractParse, rule: RuleDefinition, field: ExtractedField | None) -> RuleHit:
        now = datetime.now(timezone.utc)
        expected = rule.expression["equals"]
        if field is None:
            return self._hit(parsed, rule, RuleHitResult.INSUFFICIENT_EVIDENCE, "规则引用的字段不存在", None, None, now)
        if field.status is FieldStatus.LOW_CONFIDENCE:
            return self._hit(parsed, rule, RuleHitResult.INSUFFICIENT_EVIDENCE, f"{rule.name}证据置信度不足", field.evidence, "人工补录并重新解析", now)
        if field.status.value == expected:
            if field.status is FieldStatus.MISSING:
                evidence = FieldEvidence(0, f"未发现字段：{rule.expression['field']}", field.confidence)
                return self._hit(parsed, rule, RuleHitResult.HIT, f"缺少{rule.name}", evidence, "补充乙方主体信息后重新提交", now)
            return self._hit(parsed, rule, RuleHitResult.HIT, rule.name, field.evidence, None, now)
        return self._hit(parsed, rule, RuleHitResult.NOT_HIT, f"{rule.name}未命中", field.evidence, None, now)

    @staticmethod
    def _hit(parsed, rule, result, message, evidence, action, now):
        return RuleHit(uuid4(), parsed.id, rule.id, result, rule.severity, message, evidence, action, now)

    def _validate(self, rule: RuleDefinition) -> None:
        expression = rule.expression
        if expression.get("op") not in self.ALLOWED_OPERATIONS:
            raise RuleExpressionError("仅允许 field_status 操作")
        if set(expression) != {"op", "field", "equals"}:
            raise RuleExpressionError("规则表达式字段不在白名单内")
        if expression["equals"] not in self.ALLOWED_STATUSES:
            raise RuleExpressionError("规则状态值不在白名单内")
        if not expression["field"]:
            raise RuleExpressionError("规则字段不能为空")


def party_completeness_rule() -> RuleDefinition:
    return RuleDefinition(
        id=RULE_ID_PARTY_001,
        rule_code="RULE-PARTY-001",
        version="1.0",
        name="乙方主体完整性",
        contract_types=("after_sales", "sales"),
        severity="high",
        expression={"op": "field_status", "field": "party_b", "equals": "missing"},
        source_ref="GD-002/主体完整性要求",
        status=RuleStatus.PUBLISHED,
    )


def party_completeness_rule_v2() -> RuleDefinition:
    return RuleDefinition(
        id=RULE_ID_PARTY_002,
        rule_code="RULE-PARTY-002",
        version="1.0",
        name="甲方主体完整性",
        contract_types=("after_sales", "sales"),
        severity="high",
        expression={"op": "field_status", "field": "party_a", "equals": "missing"},
        source_ref="GD-002/主体完整性要求",
        status=RuleStatus.PUBLISHED,
    )


def warranty_clause_rule() -> RuleDefinition:
    return RuleDefinition(
        id=RULE_ID_WARRANTY_001,
        rule_code="RULE-WARRANTY-001",
        version="1.0",
        name="质保条款完整性",
        contract_types=("after_sales",),
        severity="high",
        expression={"op": "field_status", "field": "warranty_clause", "equals": "missing"},
        source_ref="GD-004/质保条款要求",
        status=RuleStatus.PUBLISHED,
    )
