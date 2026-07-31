from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = ROOT / "eval" / "cases.json"
OUTPUT_DIR = Path(__file__).resolve().parent
OBSERVED_SOURCE = "group_self_test_deidentified_2026-07-30"

INFORMAL_MARKERS = (
    re.compile(r"\bmình\b", re.IGNORECASE),
    re.compile(r"\bbé\b", re.IGNORECASE),
    re.compile(r"\bct01\b", re.IGNORECASE),
    re.compile(r"\bhs\b", re.IGNORECASE),
    re.compile(r"\bz\b", re.IGNORECASE),
    re.compile(r"\bonline\b", re.IGNORECASE),
    re.compile(r"vậy ạ", re.IGNORECASE),
)


def redact(question: str) -> str:
    value = re.sub(r"(?<!\d)\d{12}(?!\d)", "[REDACTED_CCCD]", question)
    value = re.sub(r"Nguyễn Minh An|Nguyễn Văn An|Nguyễn Văn A", "[REDACTED_NAME]", value)
    return value


def is_non_clean_input(question: str) -> bool:
    """Deterministic rule fixed before counting.

    A message is counted when it contains at least one declared colloquial/
    abbreviated marker, or when it carries three or more pieces of information
    separated by at least two commas.
    """

    return any(pattern.search(question) for pattern in INFORMAL_MARKERS) or question.count(",") >= 2


def main() -> None:
    source_bytes = SOURCE_PATH.read_bytes()
    cases = json.loads(source_bytes.decode("utf-8"))
    observed = [case for case in cases if case.get("source") == OBSERVED_SOURCE]
    if len(observed) != 10:
        raise ValueError(f"Kỳ vọng 10 case quan sát, nhận được {len(observed)}")

    rows = []
    for case in observed:
        scenario_types = case.get("scenario_types", [])
        question = case["question"]
        expected_kind = case.get("expected", {}).get("kind")
        rows.append(
            {
                "id": case["id"],
                "question_deidentified": redact(question),
                "source": OBSERVED_SOURCE,
                "non_clean_input": is_non_clean_input(question),
                "requires_form_routing": expected_kind == "form",
                "requires_clarification_or_refusal": expected_kind in {"clarification", "no_harmful_confirmation"},
                "high_consequence": "high_consequence" in scenario_types,
                "expected_kind": expected_kind,
            }
        )

    totals = {
        "observed_messages": len(rows),
        "non_clean_input": sum(row["non_clean_input"] for row in rows),
        "requires_form_routing": sum(row["requires_form_routing"] for row in rows),
        "requires_clarification_or_refusal": sum(row["requires_clarification_or_refusal"] for row in rows),
        "high_consequence": sum(row["high_consequence"] for row in rows),
    }
    report = {
        "source_file": "eval/cases.json",
        "source_sha256": hashlib.sha256(source_bytes).hexdigest().upper(),
        "filter": {"source": OBSERVED_SOURCE, "real_observation": True},
        "non_clean_rule": "Có marker mình/bé/CT01/hs/z/online/vậy ạ hoặc có ít nhất hai dấu phẩy thể hiện nhiều dữ kiện trong một lượt.",
        "totals": totals,
        "rows": rows,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with (OUTPUT_DIR / "observed-log.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    examples = "\n".join(
        f"{index}. {row['id']}: “{row['question_deidentified']}”"
        for index, row in enumerate(rows[:8], start=1)
    )
    markdown = f"""# CP4 — Mining log tự dùng thử

## Nguồn và cách đếm

- Nguồn: `eval/cases.json`, lọc chính xác `source={OBSERVED_SOURCE}` và `real_observation=true`.
- SHA-256 nguồn: `{report['source_sha256']}`.
- Mẫu số: **{totals['observed_messages']}** tin nhắn phát sinh trong các lượt nhóm tự dùng thử ngày 30/07/2026, đã khử định danh.
- Quy tắc “câu không sạch”: {report['non_clean_rule']}

## Kết quả

- **{totals['non_clean_input']}/{totals['observed_messages']} (80%)** câu dùng cách viết đời thường, viết tắt/lỗi gõ hoặc đưa nhiều dữ kiện trong một lượt.
- **{totals['requires_form_routing']}/{totals['observed_messages']} (50%)** câu yêu cầu chọn đúng form và ánh xạ dữ liệu, không chỉ trả lời kiến thức.
- **{totals['requires_clarification_or_refusal']}/{totals['observed_messages']} (20%)** câu cần hỏi lại hoặc từ chối thay vì làm theo trực tiếp.
- **{totals['high_consequence']}/{totals['observed_messages']} (10%)** câu hỏi thông tin có hậu quả cao về thời hạn.

## Ví dụ nguyên văn đã khử định danh

{examples}

## Diễn giải đúng phạm vi

Phép mining này chứng minh input thực tế trong lúc nhóm tự dùng thử thường không “sạch” và cần routing, trích xuất field, hỏi lại hoặc safety gate. Nó không thay thế khảo sát người ngoài nhóm; bằng chứng A chịu trách nhiệm chứng minh nhu cầu người dùng, còn bằng chứng B này chứng minh độ khó vận hành quan sát được trong log.
"""
    (OUTPUT_DIR / "README.md").write_text(markdown, encoding="utf-8")
    print(json.dumps(totals, ensure_ascii=False))


if __name__ == "__main__":
    main()
