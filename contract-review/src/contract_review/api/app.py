from dataclasses import asdict
from json import loads
from os import getenv
from uuid import UUID

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware

from contract_review.common.auth import (
    ROLE_ADMIN,
    SESSION_COOKIE,
    SessionManager,
    UserInfo,
    UserRepository,
)
from contract_review.common.audit import AuditService
from contract_review.common.config import load_settings, validate_production_settings
from contract_review.infrastructure.persistence.database import is_postgres_enabled
from contract_review.domain import ContractImporter, ImportRequest, InMemoryReviewStore
from contract_review.infrastructure.persistence.postgres import PostgresReviewStore
from contract_review.engine.rules.repository import RuleRepository
from contract_review.infrastructure.ocr.provider import create_ocr_provider
from contract_review.engine.parser.service import ContractParser
from contract_review.engine.parser.quality import QualityDiagnostic
from contract_review.engine.workflow.results import ReviewResultService
from contract_review.engine.rules.engine import (
    RestrictedRuleEngine,
    party_completeness_rule,
    party_completeness_rule_v2,
    warranty_clause_rule,
)
from contract_review.infrastructure.storage.object_store import ObjectStorage, create_memory_storage, create_storage
from contract_review.engine.workflow.versions import ReviewVersionService
from contract_review.engine.workflow.workflow import ContractReviewWorkflow, WorkflowError, SimulatedApprovalGateway


def _response(request_id: str, data: object = None, error: dict | None = None) -> dict[str, object]:
    return {"request_id": request_id, "ok": error is None, "data": data, "error": error}


def _error(code: str, message: str, retryable: bool = False) -> dict[str, str | bool]:
    return {"code": code, "message": message, "retryable": retryable}


def _task_data(task) -> dict:
    data = jsonable_encoder(asdict(task))
    if "external_task_key" in data and "approval_code" not in data:
        data["approval_code"] = data["external_task_key"]
    if "write_status" not in data:
        data["write_status"] = getattr(task, "write_status", "not_written")
        if hasattr(data["write_status"], "value"):
            data["write_status"] = data["write_status"].value
    try:
        data["task_status"] = task.status.to_spec() if hasattr(task.status, "to_spec") else task.status.value
    except Exception:
        data["task_status"] = data.get("status")
    return data


def _version_data(version) -> dict:
    return jsonable_encoder(asdict(version))


def _rule_data(rule) -> dict:
    return jsonable_encoder(asdict(rule))


def create_app(storage: ObjectStorage | ContractReviewWorkflow | None = None, ocr_provider=None) -> FastAPI:
    # 生产门禁：ENVIRONMENT=production 时校验关键配置，不满足则拒绝启动
    validate_production_settings(load_settings())
    if isinstance(storage, ContractReviewWorkflow):
        workflow = storage
        store = workflow.importer.store
    else:
        storage_backend = getenv("STORAGE_BACKEND", "memory").lower()
        store = PostgresReviewStore() if is_postgres_enabled() else InMemoryReviewStore()
        objects = storage or (
            create_storage() if storage_backend == "minio" else create_memory_storage()
        )
        importer = ContractImporter(store, objects)
        provider = ocr_provider or create_ocr_provider()
        workflow = ContractReviewWorkflow(
            importer,
            QualityDiagnostic(store, provider),
            ContractParser(store, provider),
            RestrictedRuleEngine(),
            ReviewResultService(store),
            ReviewVersionService(store),
            SimulatedApprovalGateway(),
        )
    app = FastAPI(title="Contract Review", version="0.3.0")

    # 认证仅在启用且后端为 PostgreSQL 时生效（用户表在库中）
    auth_enabled = getenv("AUTH_ENABLED", "false").lower() in {"1", "true", "yes"}
    auth_enabled = auth_enabled and is_postgres_enabled()

    session_manager: SessionManager | None = None
    user_repo: UserRepository | None = None
    if auth_enabled:
        user_repo = UserRepository()
        user_repo.ensure_seed_users()
        session_manager = SessionManager(
            getenv("SESSION_SECRET", "dev-session-secret-change-me"),
            int(getenv("SESSION_TTL_SECONDS", str(8 * 60 * 60))),
        )
        app.state.user_repo = user_repo
        app.state.session_manager = session_manager

    # 规则持久化：PG 启用时从 review_rules 表读取，否则回退硬编码（保持 demo 可运行）
    rule_repo: RuleRepository | None = None
    if is_postgres_enabled():
        rule_repo = RuleRepository()
        rule_repo.ensure_seed_rules()
        app.state.rule_repo = rule_repo
    audit = AuditService(store)

    def _active_rules() -> list:
        if rule_repo is not None:
            return rule_repo.list_published()
        return [party_completeness_rule(), party_completeness_rule_v2(), warranty_clause_rule()]

    cors_origins = [
        origin.strip()
        for origin in getenv("CORS_ORIGINS", "").split(",")
        if origin.strip()
    ] or [
        "http://127.0.0.1:5173", "http://localhost:5173",
        "http://127.0.0.1:5174", "http://localhost:5174",
        "http://127.0.0.1:5176", "http://localhost:5176",
        "http://127.0.0.1:8001", "http://localhost:8001",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    importer = workflow.importer
    app.state.review_store = store
    app.state.workflow = workflow

    # ── 认证辅助 ────────────────────────────────────────────────

    def _require_user(request: Request) -> UserInfo:
        """返回会话用户；未启用认证时退回 demo 匿名用户（保持演示可用）。"""
        if not auth_enabled:
            return UserInfo(id="", username="demo", display_name=None, role=ROLE_ADMIN, is_active=True)
        if session_manager is None or user_repo is None:
            raise HTTPException(status_code=401, detail=_error("UNAUTHENTICATED", "认证未配置"))
        token = request.cookies.get(SESSION_COOKIE)
        if not token:
            raise HTTPException(status_code=401, detail=_error("UNAUTHENTICATED", "未登录"))
        payload = session_manager.read(token)
        if not payload:
            raise HTTPException(status_code=401, detail=_error("UNAUTHENTICATED", "会话无效或已过期"))
        user = user_repo.get_by_id(payload["uid"])
        if user is None or not user.is_active:
            raise HTTPException(status_code=401, detail=_error("UNAUTHENTICATED", "用户不存在或已停用"))
        return user

    def _require_admin(request: Request) -> UserInfo:
        user = _require_user(request)
        if auth_enabled and user.role != ROLE_ADMIN:
            raise HTTPException(status_code=403, detail=_error("FORBIDDEN", "需要管理员权限"))
        return user

    # ── Auth Endpoints ─────────────────────────────────────────

    @app.post("/v1/auth/login")
    def login(response: Response, username: str = Form(...), password: str = Form(...)) -> dict[str, object]:
        if not auth_enabled:
            return _response("req_login", error=_error("AUTH_DISABLED", "认证未启用"))
        user = user_repo.verify_credentials(username, password)
        if user is None:
            return _response("req_login", error=_error("INVALID_CREDENTIALS", "用户名或密码错误"))
        token = session_manager.create(user)
        response.set_cookie(
            SESSION_COOKIE, token, httponly=True, samesite="lax", max_age=session_manager.max_age
        )
        return _response("req_login", {
            "user": {
                "id": user.id, "username": user.username,
                "display_name": user.display_name, "role": user.role,
            }
        })

    @app.post("/v1/auth/logout")
    def logout(response: Response) -> dict[str, object]:
        response.delete_cookie(SESSION_COOKIE)
        return _response("req_logout", {"status": "ok"})

    @app.get("/v1/auth/me")
    def me(request: Request) -> dict[str, object]:
        if not auth_enabled:
            # 与 _require_user 回退一致：demo 模式返回匿名管理员，保持演示可用
            demo = UserInfo(id="", username="demo", display_name="演示用户", role=ROLE_ADMIN, is_active=True)
            return _response("req_me", {
                "authenticated": True,
                "user": {"id": demo.id, "username": demo.username, "display_name": demo.display_name, "role": demo.role},
            })
        try:
            user = _require_user(request)
        except HTTPException:
            return _response("req_me", {"authenticated": False, "user": None})
        return _response("req_me", {
            "authenticated": True,
            "user": {"id": user.id, "username": user.username, "display_name": user.display_name, "role": user.role},
        })

    # ── Core Endpoints ──────────────────────────────────────────

    @app.get("/v1/health")
    async def health() -> dict[str, object]:
        return _response("req_health", {"service": "contract-review", "status": "ok"})

    @app.get("/v1/tasks")
    async def list_tasks() -> dict[str, object]:
        tasks = sorted(store.list_tasks(), key=lambda item: item.updated_at, reverse=True)
        return _response("req_tasks", {"items": [_task_data(t) for t in tasks], "total": len(tasks)})

    @app.get("/v1/tasks/{task_id}")
    async def get_task(task_id: UUID) -> dict[str, object]:
        task = store.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=_error("TASK_NOT_FOUND", "任务不存在"))
        attachments = [jsonable_encoder(asdict(a)) for a in store.list_attachments(task_id)]
        return _response("req_task", {"task": _task_data(task), "attachments": attachments})

    @app.get("/v1/tasks/{task_id}/versions")
    @app.get("/v1/reviews/{task_id}/versions")
    async def list_versions(task_id: UUID) -> dict[str, object]:
        if store.get_task(task_id) is None:
            raise HTTPException(status_code=404, detail=_error("TASK_NOT_FOUND", "任务不存在"))
        versions = [_version_data(v) for v in workflow.versions.list_versions(task_id)]
        return _response("req_versions", {"task_id": str(task_id), "items": versions, "total": len(versions)})

    @app.get("/v1/tasks/{task_id}/versions/{version_id}")
    @app.get("/v1/reviews/{task_id}/versions/{version_id}")
    async def restore_version_view(task_id: UUID, version_id: UUID) -> dict[str, object]:
        task = store.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=_error("TASK_NOT_FOUND", "任务不存在"))
        try:
            context = workflow.versions.restore_view(task, version_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=_error("VERSION_NOT_FOUND", str(exc))) from exc
        version = workflow.versions.get_version(version_id)
        return _response("req_version_view", {"version": _version_data(version), "view_context": jsonable_encoder(asdict(context))})

    @app.post("/v1/imports")
    async def import_contract(
        external_task_key: str = Form(...),
        title: str = Form(...),
        applicant_id: str = Form(...),
        file: UploadFile = File(...),
        request_id: str = Form("req_local"),
    ) -> dict[str, object]:
        result = importer.import_contract(
            ImportRequest(
                external_task_key=external_task_key,
                title=title,
                applicant_id=applicant_id,
                file_name=file.filename or "contract.pdf",
                mime_type=file.content_type or "application/octet-stream",
                content=await file.read(),
            ),
            request_id,
        )
        if result.error_code:
            return _response(request_id, {"task_id": str(result.task.id), "status": result.task.status.value}, _error(result.error_code, result.error_message or result.error_code))
        return _response(request_id, {
            "task": _task_data(result.task),
            "attachment": jsonable_encoder(asdict(result.attachment)) if result.attachment else None,
            "duplicate": result.duplicate,
        })

    @app.post("/v1/reviews/run")
    async def run_review(
        request: Request,
        external_task_key: str = Form(...),
        title: str = Form(...),
        applicant_id: str = Form(...),
        file: UploadFile = File(...),
        confirmations: str = Form(...),
        actor_id: str = Form(""),
        request_id: str = Form("req_local"),
    ) -> dict[str, object]:
        current_user = _require_user(request)
        # 认证模式下操作人身份来自会话，禁止前端表单伪造 actor_id
        effective_actor = current_user.username if auth_enabled else actor_id
        if auth_enabled and not effective_actor:
            raise HTTPException(status_code=401, detail=_error("UNAUTHENTICATED", "缺少操作人身份"))
        try:
            raw = loads(confirmations)
            normalized = {}
            for role, value in raw.items():
                if isinstance(value, dict):
                    conf_actor, comment = value["actor_id"], value["comment"]
                else:
                    conf_actor, comment = value[0], value[1]
                # 认证模式下：使用登录用户作为会签人，忽略前端传入的 actor_id
                normalized[role] = (effective_actor, comment)
            outcome = workflow.run(
                ImportRequest(external_task_key, title, applicant_id, file.filename or "contract.pdf", file.content_type or "application/pdf", await file.read()),
                _active_rules(),
                normalized, effective_actor, request_id,
            )
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            return _response(request_id, error=_error("INVALID_CONFIRMATIONS", str(exc)))
        except WorkflowError as exc:
            return _response(request_id, error=_error("REVIEW_WORKFLOW_FAILED", str(exc)))
        return _response(request_id, {
            "task_id": outcome.task_id,
            "attachment_id": outcome.attachment_id,
            "review_status": outcome.review.status.value,
            "version_id": str(outcome.version.id),
            "writeback": jsonable_encoder(asdict(outcome.writeback)),
            "duplicate": outcome.duplicate,
            "review": asdict(outcome.review),
            "version": asdict(outcome.version),
            "parse": asdict(outcome.parse),
        })

    # ── Rules API ───────────────────────────────────────────────

    @app.get("/v1/rules")
    async def list_rules() -> dict[str, object]:
        rules = _active_rules()
        return _response("req_rules", {
            "items": [_rule_data(r) for r in rules],
            "total": len(rules),
        })

    @app.post("/v1/rules")
    async def add_rule(request: Request, rule_code: str = Form(...), name: str = Form(...), severity: str = Form("medium")) -> dict[str, object]:
        _require_admin(request)
        if severity not in ("low", "medium", "high"):
            return _response("req_rule", error=_error("INVALID_SEVERITY", f"severity 必须为 low/medium/high"))
        if rule_repo is None:
            return _response("req_rule", {"rule_code": rule_code, "name": name, "severity": severity, "status": "draft"})
        rule = rule_repo.create_rule(rule_code, name, severity)
        return _response("req_rule", _rule_data(rule))

    @app.patch("/v1/rules/{rule_id}")
    async def update_rule(request: Request, rule_id: UUID, status: str = Form(...)) -> dict[str, object]:
        user = _require_admin(request)
        if status not in ("draft", "published", "retired"):
            return _response("req_rule", error=_error("INVALID_STATUS", "status 必须为 draft/published/retired"))
        if rule_repo is None:
            return _response("req_rule", error=_error("RULES_NOT_PERSISTED", "规则持久化未启用"))
        rule = rule_repo.set_status(rule_id, status, approved_by=user.username)
        if rule is None:
            raise HTTPException(status_code=404, detail=_error("RULE_NOT_FOUND", "规则不存在"))
        return _response("req_rule", _rule_data(rule))

    # ── Audit API ───────────────────────────────────────────────

    @app.get("/v1/audit/events")
    async def list_audit_events(limit: int = 50, offset: int = 0) -> dict[str, object]:
        logs = audit.list_events(limit, offset)
        return _response("req_audit", {
            "items": [jsonable_encoder(asdict(log)) for log in logs],
            "total": len(logs),
            "limit": limit,
            "offset": offset,
        })

    @app.get("/v1/tasks/{task_id}/audit")
    async def task_audit(task_id: UUID) -> dict[str, object]:
        task = store.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=_error("TASK_NOT_FOUND", "任务不存在"))
        logs = [jsonable_encoder(asdict(log)) for log in audit.list_for_task(task_id)]
        return _response("req_task_audit", {"task_id": str(task_id), "items": logs, "total": len(logs)})

    # ── Tools API (2.4.10) & Agent API ────────────────────────────
    @app.get("/v1/approvals/pending")
    async def list_pending_contract_approvals(limit: int = 10) -> dict[str, object]:
        from contract_review.application.tools.contract_tools import list_pending_contract_approvals as _list
        data = _list(store, limit=limit)
        return _response("req_pending", data)

    @app.get("/v1/approvals/{instance_id}")
    async def get_contract_approval(instance_id: str) -> dict[str, object]:
        from contract_review.application.tools.contract_tools import get_contract_approval as _get
        try:
            data = _get(store, instance_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=_error("APPROVAL_NOT_FOUND", str(exc))) from exc
        return _response("req_approval", data)

    @app.post("/v1/approvals/{instance_id}/attachments/{attachment_id}/download")
    async def download_contract_attachment(instance_id: str, attachment_id: str) -> dict[str, object]:
        from contract_review.application.tools.contract_tools import download_contract_attachment as _dl
        data = _dl(store, instance_id, attachment_id)
        if "file_content" in data:
            data = {k: v for k, v in data.items() if k != "file_content"}
        return _response("req_download", data)

    @app.post("/v1/tools/parse")
    async def parse_contract_document(document_id: str = Form(...)) -> dict[str, object]:
        from contract_review.application.tools.contract_tools import parse_contract_document as _parse
        content = None
        try:
            att = store.get_attachment(UUID(document_id))
            if att is not None:
                try:
                    content = workflow.importer.objects.get(att.storage_key)
                except Exception:
                    content = None
        except Exception:
            content = None
        data = _parse(store, workflow.parser, document_id, content)
        return _response("req_parse", data)

    @app.post("/v1/tools/rules")
    async def run_contract_rules(case_id: str = Form(...)) -> dict[str, object]:
        from contract_review.application.tools.contract_tools import run_contract_rules as _run
        try:
            data = _run(store, workflow.rules, _active_rules(), case_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=_error("CASE_NOT_FOUND", str(exc))) from exc
        return _response("req_rules_run", data)

    @app.post("/v1/tools/result")
    async def save_review_result(case_id: str = Form(...), overall_risk_level: str = Form(...), summary_text: str = Form(...), focus_points_json: str = Form("[]"), comment_text: str = Form(...)) -> dict[str, object]:
        from contract_review.application.tools.contract_tools import save_review_result as _save
        import json as _json
        try:
            focus = _json.loads(focus_points_json) if focus_points_json else []
        except Exception:
            focus = []
        try:
            data = _save(store, case_id, overall_risk_level, summary_text, focus, comment_text)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=_error("CASE_NOT_FOUND", str(exc))) from exc
        return _response("req_save_result", data)

    @app.post("/v1/approvals/{instance_id}/comments/write")
    async def write_approval_comment(instance_id: str, review_id: str = Form(...)) -> dict[str, object]:
        from contract_review.application.tools.contract_tools import write_approval_comment as _write
        try:
            data = _write(store, instance_id, review_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=_error("WRITE_FAILED", str(exc))) from exc
        return _response("req_write", data)

    @app.post("/v1/agent/run")
    async def agent_run(instance_id: str = Form(...)) -> dict[str, object]:
        from contract_review.application.agent.review_agent import ContractReviewAgent
        agent = ContractReviewAgent(store, workflow.parser, workflow.rules, _active_rules())
        result = agent.run_full_loop(instance_id)
        return _response("req_agent", {"instance_id": result.instance_id, "final_status": result.final_status, "overall_risk_level": result.overall_risk_level, "summary_text": result.summary_text, "blocked_reason": result.blocked_reason, "trajectory": [asdict(s) for s in result.trajectory]})

    @app.post("/v1/tasks/{task_id}/retry")
    async def retry_blocked(task_id: UUID) -> dict[str, object]:
        task = store.get_task(task_id)
        if task is None:
            task = store.find_task(str(task_id))
        if task is None:
            raise HTTPException(status_code=404, detail=_error("TASK_NOT_FOUND", "任务不存在"))
        try:
            task.retry()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=_error("RETRY_NOT_ALLOWED", str(exc))) from exc
        store.save_task(task)
        return _response("req_retry", {"task_id": str(task.id), "status": task.status.value, "write_status": getattr(task, "write_status", "not_written").value if hasattr(task, "write_status") else "not_written"})

    # ── Review Detail API（评审工作台数据源）────────────────────

    # ── Insights APIs — 让项目更饱满（证据图谱/风险矩阵/审批流）──
    @app.get("/v1/tasks/{task_id}/evidence-graph")
    async def evidence_graph(task_id: UUID) -> dict[str, object]:
        task = store.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=_error("TASK_NOT_FOUND", "任务不存在"))
        parse = store.get_parse_for_task(task_id)
        if parse is None:
            return _response("req_evidence_graph", {"nodes": [], "edges": [], "empty_reason": "尚未解析"})
        payload = getattr(parse, "extracted_payload", {}) or {}
        hits = store.list_rule_hits(parse.id)
        nodes: list[dict] = []
        edges: list[dict] = []
        for key, field in payload.items():
            fid = f"field:{key}"
            nodes.append({"id": fid, "type": "field", "label": key, "status": getattr(field, "status", "unknown"), "value": getattr(field, "value", None), "evidence": getattr(getattr(field, "evidence", None), "snippet", None)})
            for h in hits:
                evidence_text = getattr(h, "evidence_text", "") or ""
                snippet = getattr(getattr(field, "evidence", None), "snippet", "") or ""
                if snippet and snippet[:8] in evidence_text or key in getattr(h, "message", ""):
                    hid = f"hit:{h.id}"
                    if not any(n["id"] == hid for n in nodes):
                        nodes.append({"id": hid, "type": "hit", "label": getattr(h, "message", str(h.id))[:24], "severity": getattr(h, "severity", "low")})
                    edges.append({"from": fid, "to": hid, "label": "supports"})
        for h in hits:
            hid = f"hit:{h.id}"
            if not any(n["id"] == hid for n in nodes):
                nodes.append({"id": hid, "type": "hit", "label": getattr(h, "message", str(h.id))[:24], "severity": getattr(h, "severity", "low")})
        return _response("req_evidence_graph", {"task_id": str(task_id), "nodes": nodes, "edges": edges, "total_fields": len(payload), "total_hits": len(hits)})

    @app.get("/v1/tasks/{task_id}/risk-matrix")
    async def risk_matrix(task_id: UUID) -> dict[str, object]:
        task = store.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=_error("TASK_NOT_FOUND", "任务不存在"))
        parse = store.get_parse_for_task(task_id)
        hits = store.list_rule_hits(parse.id) if parse else []
        # 维度：severity x rule_code
        matrix: dict = {"high": [], "medium": [], "low": []}
        for h in hits:
            sev = getattr(h, "severity", "low")
            if sev not in matrix:
                sev = "low"
            matrix[sev].append({"rule_id": str(getattr(h, "rule_id", "")), "message": getattr(h, "message", ""), "suggested_action": getattr(h, "suggested_action", None), "evidence_position": getattr(h, "evidence_position", None)})
        total = len(hits)
        level = "low"
        if matrix["high"]:
            level = "high"
        elif matrix["medium"]:
            level = "medium"
        return _response("req_risk_matrix", {"task_id": str(task_id), "overall_risk_level": level, "matrix": matrix, "total": total, "counts": {k: len(v) for k, v in matrix.items()}})

    @app.get("/v1/tasks/{task_id}/flow")
    async def approval_flow(task_id: UUID) -> dict[str, object]:
        task = store.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=_error("TASK_NOT_FOUND", "任务不存在"))
        logs = [jsonable_encoder(asdict(l)) for l in store.list_logs_for_task(task_id)]
        # 规范流：pending -> parsing -> reviewing -> done / blocked
        flow_nodes = [
            {"key": "pending", "label": "待处理", "status": "done"},
            {"key": "parsing", "label": "解析中", "status": "pending"},
            {"key": "reviewing", "label": "评审中", "status": "pending"},
            {"key": "done", "label": "已完成", "status": "pending"},
        ]
        cur = getattr(task.status, "to_spec", lambda: task.status.value)() if hasattr(task.status, "to_spec") else task.status.value
        order = ["pending", "parsing", "reviewing", "done", "blocked"]
        try:
            cur_idx = order.index(cur)
        except ValueError:
            cur_idx = 0
        for i, n in enumerate(flow_nodes):
            if cur == "blocked":
                n["status"] = "blocked" if i == len(flow_nodes) - 1 else "done"
            elif i < cur_idx:
                n["status"] = "done"
            elif i == cur_idx:
                n["status"] = "current"
        if cur == "blocked":
            flow_nodes.append({"key": "blocked", "label": "阻塞", "status": "blocked", "reason": task.blocked_reason})
        return _response("req_flow", {"task_id": str(task_id), "current_status": cur, "write_status": getattr(task, "write_status", "not_written").value if hasattr(getattr(task, "write_status", ""), "value") else str(getattr(task, "write_status", "not_written")), "flow": flow_nodes, "logs": logs[:20]})

    @app.get("/v1/tasks/{task_id}/review")
    async def get_task_review(task_id: UUID) -> dict[str, object]:
        task = store.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=_error("TASK_NOT_FOUND", "任务不存在"))
        attachments = [jsonable_encoder(asdict(a)) for a in store.list_attachments(task_id)]
        versions = [_version_data(v) for v in workflow.versions.list_versions(task_id)]
        latest = versions[-1] if versions else None
        # 从持久化存储读取评审结论（容器重启后仍然可用）
        result = store.find_confirmed_result(task_id)
        review = jsonable_encoder(asdict(result)) if result is not None else None
        parse = None
        rule_hits = []
        if result is not None:
            stored_parse = store.get_parse_for_task(task_id)
            if stored_parse is not None:
                parse = jsonable_encoder(asdict(stored_parse))
                rule_hits = [
                    jsonable_encoder(asdict(h)) for h in store.list_rule_hits(stored_parse.id)
                ]
        return _response("req_task_review", {
            "task": _task_data(task),
            "attachments": attachments,
            "latest_version": latest,
            "review": review,
            "parse": parse,
            "rule_hits": rule_hits,
            "version_count": len(versions),
        })

    return app


app = create_app()