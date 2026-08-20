"""一键写入 Mock 审批待办到当前 Store（不依赖真实审批系统）。"""
from contract_review.domain import InMemoryReviewStore
from contract_review.mock_approvals import list_mock_approvals

def seed(store: InMemoryReviewStore, limit: int = 15) -> int:
    items = list_mock_approvals(limit=limit)
    for it in items:
        print(f"{it['approval_code']} | {it['title']} | {it['applicant_name']} | 附件{it['attachment_count']}")
    return len(items)

if __name__ == "__main__":
    print(seed(InMemoryReviewStore()))
