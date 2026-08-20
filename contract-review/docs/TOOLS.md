# 工具调用说明（2.4.10）

| 工具 | 接口 | 说明 |
|------|------|------|
| list_pending_contract_approvals(limit) | GET /v1/approvals/pending | 拉取待办，含 approval_code/title/applicant/apply_time/attachment_count，自动去重 |
| get_contract_approval(instance_id) | GET /v1/approvals/{id} | 单个审批详情：表单数据、附件清单、状态 |
| download_contract_attachment(instance_id, attachment_id, file_name) | POST /v1/approvals/{id}/attachments/{att}/download | 返回 file_path + file_sha256 |
| parse_contract_document(document_id) | POST /v1/tools/parse | 解析字段、原文片段、定位；失败进 blocked |
| run_contract_rules(case_id) | POST /v1/tools/rules | 规则命中、风险等级、证据位置、建议 |
| save_review_result(case_id, overall_risk_level, summary_text, focus_points_json, comment_text) | POST /v1/tools/result | 保存 overall_risk_level/summary/focus/comment |
| write_approval_comment(instance_id, review_id) | POST /v1/approvals/{id}/comments/write | 写回评论区，返回 write_status |

**一键闭环**：POST /v1/agent/run {instance_id} 串起 6 步并输出轨迹。

**重试**：POST /v1/tasks/{task_id}/retry 仅 blocked 可重试，回 parsing。
