from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from contract_review.domain import ContractImporter, ImportRequest, QualityStatus, TaskStatus
from contract_review.parser import ContractParse, ContractParser, ParseStatus
from contract_review.quality import QualityDiagnostic
from contract_review.results import ReviewResult, ReviewResultService
from contract_review.rules import RuleDefinition, RestrictedRuleEngine
from contract_review.versions import ReviewVersion, ReviewVersionService


class WorkflowError(RuntimeError):
    pass


@dataclass(frozen=True)
class SimulatedWriteback:
    code: str
    task_id: str
    version_id: str
    recommendation: str
    request_id: str


class WritebackGateway(Protocol):
    def write(self, task_id: str, version: ReviewVersion, request_id: str) -> SimulatedWriteback: ...


class SimulatedApprovalGateway:
    """阶段 2 的回写边界：只记录模拟结果，绝不访问真实审批系统。"""

    def __init__(self) -> None:
        self.calls: list[SimulatedWriteback] = []
        self._by_key: dict[str, SimulatedWriteback] = {}

    def write(self, task_id: str, version: ReviewVersion, request_id: str) -> SimulatedWriteback:
        key = f"{task_id}:{version.id}"
        if key in self._by_key:
            return self._by_key[key]
        response = SimulatedWriteback("SIMULATED_ONLY", task_id, str(version.id), version.recommendation.value, request_id)
        self._by_key[key] = response
        self.calls.append(response)
        return response


@dataclass(frozen=True)
class WorkflowRun:
    task_id: str
    attachment_id: str
    parse: ContractParse
    review: ReviewResult
    version: ReviewVersion
    writeback: SimulatedWriteback
    duplicate: bool


class ContractReviewWorkflow:
    def __init__(
        self,
        importer: ContractImporter,
        quality: QualityDiagnostic,
        parser: ContractParser,
        rules: RestrictedRuleEngine,
        results: ReviewResultService,
        versions: ReviewVersionService,
        writeback: WritebackGateway,
    ) -> None:
        self.importer = importer
        self.quality = quality
        self.parser = parser
        self.rules = rules
        self.results = results
        self.versions = versions
        self.writeback = writeback
        self._completed: dict[str, WorkflowRun] = {}

    def run(
        self,
        request: ImportRequest,
        rule_definitions: list[RuleDefinition],
        confirmations: dict[str, tuple[str, str]],
        actor_id: str,
        request_id: str = "req_local",
    ) -> WorkflowRun:
        idempotency_key = f"{request.external_task_key}:{sha256(request.content).hexdigest()}"
        previous = self._completed.get(idempotency_key)
        if previous is not None:
            return WorkflowRun(previous.task_id, previous.attachment_id, previous.parse, previous.review, previous.version, previous.writeback, True)

        imported = self.importer.import_contract(request, request_id)
        if imported.error_code or imported.attachment is None:
            raise WorkflowError(imported.error_message or imported.error_code or "导入失败")
        attachment = imported.attachment
        task = imported.task
        content = self.importer.objects.get(attachment.storage_key)

        quality = self.quality.diagnose(task, attachment, content, request_id)
        if quality.status is not QualityStatus.USABLE:
            raise WorkflowError(quality.blocked_reason or "文件质量不满足解析条件")
        parsed = self.parser.parse(task, attachment, content, request_id)
        if parsed.status is not ParseStatus.SUCCEEDED:
            raise WorkflowError(parsed.error_message or parsed.error_code or "解析失败")
        hits = self.rules.run(parsed, rule_definitions, request_id)
        for hit in hits:
            self.importer.store.save_rule_hit(hit)
        review = self.results.create_recommendation(task, attachment, hits, actor_id, request_id)
        for role in review.required_roles:
            confirmation = confirmations.get(role)
            if confirmation is None:
                raise WorkflowError(f"缺少会签角色：{role}")
            confirmer, comment = confirmation
            self.results.confirm_role(review, task, role, confirmer, comment, request_id)
        self.results.finalize(review, task, actor_id, request_id)
        version = self.versions.save(task, review, actor_id, request_id)
        writeback = self.writeback.write(str(task.id), version, request_id)
        run = WorkflowRun(str(task.id), str(attachment.id), parsed, review, version, writeback, False)
        self._completed[idempotency_key] = run
        return run
