from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import zipfile
from collections import Counter
from pathlib import Path


PII_PATTERNS = (
    re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
    re.compile(r"(?<!\d)(?:\+?84|0)\d{8,10}(?!\d)"),
    re.compile(r"(?<!\d)\d{12}(?!\d)"),
)


def redact(text: str, names: list[str]) -> tuple[str, int]:
    value = text
    replacements = 0
    for pattern in PII_PATTERNS:
        value, count = pattern.subn("[REDACTED]", value)
        replacements += count
    for name in names:
        if len(name) < 4:
            continue
        value, count = re.subn(re.escape(name), "[REDACTED_NAME]", value, flags=re.IGNORECASE)
        replacements += count
    return value, replacements


def split_choices(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Khử định danh và phân tích khảo sát CP4.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    source_bytes = args.zip_path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(source_bytes)) as archive:
        csv_entries = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(csv_entries) != 1:
            raise ValueError("ZIP phải chứa đúng một file CSV")
        csv_text = archive.read(csv_entries[0]).decode("utf-8-sig")

    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)
    if len(rows) != 45:
        raise ValueError(f"Kỳ vọng 45 phản hồi, nhận được {len(rows)}")

    columns = reader.fieldnames or []
    if len(columns) != 9:
        raise ValueError(f"Kỳ vọng 9 cột, nhận được {len(columns)}")

    name_col = columns[1]
    age_col = columns[2]
    profession_col = columns[3]
    online_col = columns[4]
    travel_col = columns[5]
    service_col = columns[6]
    overall_col = columns[7]
    open_col = columns[8]

    names = sorted({(row[name_col] or "").strip() for row in rows if (row[name_col] or "").strip()}, key=len, reverse=True)
    output_rows: list[dict[str, str]] = []
    redaction_count = 0
    counters = {
        "online": Counter(),
        "travel": Counter(),
        "service": Counter(),
        "overall": Counter(),
        "age": Counter(),
        "profession": Counter(),
    }

    for index, row in enumerate(rows, start=1):
        feedback, replacements = redact((row[open_col] or "").strip(), names)
        redaction_count += replacements
        output_rows.append(
            {
                "respondent_id": f"R{index:03d}",
                "age_band": (row[age_col] or "").strip(),
                "profession": (row[profession_col] or "").strip(),
                "online_pain_points": (row[online_col] or "").strip(),
                "travel_pain_points": (row[travel_col] or "").strip(),
                "service_pain_points": (row[service_col] or "").strip(),
                "overall_pain_points": (row[overall_col] or "").strip(),
                "open_feedback": feedback,
            }
        )
        counters["age"][(row[age_col] or "").strip()] += 1
        counters["profession"][(row[profession_col] or "").strip()] += 1
        for key, column in (
            ("online", online_col),
            ("travel", travel_col),
            ("service", service_col),
            ("overall", overall_col),
        ):
            counters[key].update(split_choices(row[column] or ""))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    deidentified_path = args.output_dir / "responses-deidentified.csv"
    with deidentified_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)

    aggregate_rows: list[dict[str, object]] = []
    for category in ("online", "travel", "service", "overall", "age", "profession"):
        for option, count in counters[category].most_common():
            aggregate_rows.append(
                {
                    "category": category,
                    "option": option,
                    "count": count,
                    "denominator": len(rows),
                    "rate": count / len(rows),
                }
            )
    aggregate_path = args.output_dir / "aggregate-results.csv"
    with aggregate_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(aggregate_rows[0]))
        writer.writeheader()
        writer.writerows(aggregate_rows)

    report = {
        "source_zip_sha256": hashlib.sha256(source_bytes).hexdigest().upper(),
        "response_count": len(rows),
        "removed_columns": [columns[0], name_col],
        "output_columns": list(output_rows[0]),
        "pii_replacements_in_open_feedback": redaction_count,
        "counts": {key: dict(value) for key, value in counters.items()},
    }
    (args.output_dir / "analysis.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(json.dumps({
        "rows": len(rows),
        "deidentified_csv": str(deidentified_path),
        "aggregate_csv": str(aggregate_path),
        "pii_replacements": redaction_count,
        "source_zip_sha256": report["source_zip_sha256"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
