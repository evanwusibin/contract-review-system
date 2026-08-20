from pathlib import Path
from contract_review.mock_approvals import mock_attachment_content

out = Path(__file__).resolve().parent.parent / "examples"
out.mkdir(exist_ok=True)
for code in ["CTR-2026-0001", "CTR-2026-0003", "CTR-2026-0009"]:
    data = mock_attachment_content(code, f"{code}-ATT-01")
    (out / f"{code}.pdf").write_bytes(data)
    print(f"wrote {out / f'{code}.pdf'}")
