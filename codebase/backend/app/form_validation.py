"""Pure rule-based validation for a form draft — no LLM, no database.

Rules and Vietnamese messages come entirely from the field schema loaded via
`app.procedure_settings.get_procedure_settings().form_candidates`; this module
contains no hardcoded business text.
"""

import hashlib
import json
import re
from datetime import UTC, date, datetime
from uuid import uuid4

from app.agent_runtime import assess_prompt_injection
from app.procedure_catalog import normalize_text
from app.procedure_settings import CrossFieldRule, FormCandidate, FormField
from app.schemas import ValidationIssue, ValidationResult, ValidationSummary

_EMPTY_VALUES = (None, "", [], {})
_SECRET_VALUE = re.compile(r"(?i)(?:\bsk-[A-Za-z0-9_-]{16,}\b|\bBearer\s+[A-Za-z0-9._~+/-]{12,}=*)")
_PLACEHOLDER_VALUES = {"test", "testing", "xxx", "fake", "không biết", "chưa biết"}
_PLACEHOLDER_NAME_TOKENS = {"abc", "aaa", "xxx", "xyz", "zzz", "test", "testing", "fake", "demo"}
_RELATIONSHIP_MARKERS = (
    "cha", "bo", "me", "con", "ong", "ba", "anh", "chi", "em", "vo", "chong",
    "nguoi giam ho", "nguoi than", "nguoi duoc khai sinh",
)


def canonical_input_hash(values: dict) -> str:
    canonical = json.dumps(values, sort_keys=True, ensure_ascii=False)
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def _is_empty(value: object) -> bool:
    return value in _EMPTY_VALUES


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _issue(field: FormField, issue_code: str, *, severity: str | None = None, message_vi: str | None = None) -> ValidationIssue:
    return ValidationIssue(
        issue_code=issue_code,
        rule_code=field.validation.rule_code,
        field_code=field.field_code,
        severity=severity or field.validation.severity,
        message_vi=message_vi or field.validation.message_vi,
        suggestion_vi=field.validation.suggestion_vi,
    )


def _check_field(field: FormField, value: object) -> ValidationIssue | None:
    empty = _is_empty(value)
    if field.required and empty:
        return _issue(field, "FIELD_REQUIRED", severity="blocking_error")
    if empty:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if assess_prompt_injection(stripped).blocked:
            return ValidationIssue(
                issue_code="UNTRUSTED_INSTRUCTION_BLOCKED",
                rule_code="SECURITY_UNTRUSTED_INSTRUCTION",
                field_code=field.field_code,
                severity="blocking_error",
                message_vi=f"{field.label_vi} chứa chỉ dẫn điều khiển hệ thống/tool và đã bị chặn.",
                suggestion_vi="Chỉ nhập dữ liệu hành chính cần thiết, không nhập lệnh dành cho AI hoặc tool.",
            )
        if _SECRET_VALUE.search(stripped):
            return ValidationIssue(
                issue_code="SECRET_VALUE_BLOCKED",
                rule_code="SECURITY_DLP_SECRET",
                field_code=field.field_code,
                severity="blocking_error",
                message_vi=f"{field.label_vi} có chuỗi giống khóa truy cập và không được đưa vào hồ sơ.",
                suggestion_vi="Xóa khóa truy cập/token và đổi khóa nếu đây là dữ liệu thật.",
            )
        if field.required and stripped.casefold() in _PLACEHOLDER_VALUES:
            return ValidationIssue(
                issue_code="PLACEHOLDER_VALUE_BLOCKED",
                rule_code="DATA_PLACEHOLDER",
                field_code=field.field_code,
                severity="blocking_error",
                message_vi=f"{field.label_vi} đang chứa dữ liệu giữ chỗ, chưa thể dùng để nộp.",
                suggestion_vi="Thay bằng thông tin thực tế và kiểm tra lại.",
            )
        if field.field_code.endswith("full_name"):
            name_tokens = set(re.findall(r"[a-z]+", normalize_text(stripped)))
            if name_tokens & _PLACEHOLDER_NAME_TOKENS:
                return ValidationIssue(
                    issue_code="NAME_PLACEHOLDER_BLOCKED",
                    rule_code="DATA_NAME_SANITY",
                    field_code=field.field_code,
                    severity="blocking_error",
                    message_vi=f"{field.label_vi} có dấu hiệu là dữ liệu thử hoặc chuỗi giữ chỗ.",
                    suggestion_vi="Nhập họ tên đúng như trên giấy tờ hoặc thông tin thực tế cần đăng ký.",
                )
        if field.field_code == "relationship_to_child":
            relationship = normalize_text(stripped)
            matched_relations = {
                marker for marker in _RELATIONSHIP_MARKERS
                if re.search(rf"(?<![a-z0-9]){re.escape(marker)}(?![a-z0-9])", relationship)
            }
            # A single requester cannot simultaneously have two conflicting
            # relationships such as "ông cố - con" to the same person.
            if len(matched_relations) > 1:
                return ValidationIssue(
                    issue_code="RELATIONSHIP_CONTRADICTORY",
                    rule_code="DATA_RELATIONSHIP_SANITY",
                    field_code=field.field_code,
                    severity="blocking_error",
                    message_vi="Quan hệ với người được khai sinh đang chứa nhiều vai trò mâu thuẫn.",
                    suggestion_vi="Chỉ nhập một quan hệ của người yêu cầu, ví dụ: cha, mẹ, ông, bà hoặc người giám hộ.",
                )
        if "citizen_id" in field.field_code and re.fullmatch(r"(\d)\1{8,11}", stripped):
            return ValidationIssue(
                issue_code="IDENTIFIER_REPEATED_DIGIT",
                rule_code="DATA_IDENTIFIER_SANITY",
                field_code=field.field_code,
                severity="blocking_error",
                message_vi=f"{field.label_vi} có mẫu số lặp bất thường.",
                suggestion_vi="Đối chiếu lại số định danh trên giấy tờ gốc.",
            )
    if field.data_type == "enum" and field.validation.enum_values and value not in field.validation.enum_values:
        return _issue(field, "FIELD_ENUM_INVALID", severity="blocking_error")
    if field.validation.regex and isinstance(value, str) and not re.fullmatch(field.validation.regex, value.strip()):
        return _issue(field, "FIELD_FORMAT_INVALID")
    if field.validation.max_length and isinstance(value, str) and len(value) > field.validation.max_length:
        return _issue(field, "FIELD_TOO_LONG")
    if field.data_type == "date" and field.validation.not_future_date:
        parsed = _parse_date(value)
        if parsed is None:
            return _issue(field, "FIELD_DATE_UNPARSEABLE", severity="blocking_error", message_vi=f"Định dạng ngày của {field.label_vi.lower()} không hợp lệ, cần dạng YYYY-MM-DD.")
        if parsed > date.today():
            return _issue(field, "FIELD_DATE_IN_FUTURE", severity="blocking_error")
    if field.validation.not_future_year and isinstance(value, str) and re.fullmatch(r"\d{4}", value.strip()):
        if int(value.strip()) > date.today().year:
            return _issue(field, "FIELD_YEAR_IN_FUTURE", severity="blocking_error")
    return None


def validate_field_updates(
    candidate: FormCandidate,
    known_values: dict,
    updates: dict[str, object],
) -> list[ValidationIssue]:
    """Validate newly extracted chat slots before they enter the trusted draft."""

    values = {**known_values, **updates}
    issues: list[ValidationIssue] = []
    for field_code, value in updates.items():
        field = candidate.field_by_code(field_code)
        if field is not None and (issue := _check_field(field, value)) is not None:
            issues.append(issue)
    updated_codes = set(updates)
    for rule in candidate.cross_field_rules:
        involved = {rule.older_field_code, rule.younger_field_code, rule.anchor_field_code}
        if updated_codes & involved and (issue := _check_cross_field_rule(rule, values)) is not None:
            issues.append(issue)
    return issues


def _extract_year(value: object) -> int | None:
    """A cross-field rule's endpoints may each be a full ISO date or a bare 4-digit year."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    parsed = _parse_date(text)
    if parsed is not None:
        return parsed.year
    if re.fullmatch(r"\d{4}", text):
        return int(text)
    return None


def _check_cross_field_rule(rule: CrossFieldRule, values: dict) -> ValidationIssue | None:
    older_year = _extract_year(values.get(rule.older_field_code))
    younger_year = _extract_year(values.get(rule.younger_field_code))
    if older_year is None or younger_year is None:
        return None
    if older_year > younger_year - rule.min_gap_years:
        return ValidationIssue(
            issue_code="CROSS_FIELD_MIN_AGE_GAP",
            rule_code=rule.rule_code,
            field_code=rule.anchor_field_code,
            severity=rule.severity,
            message_vi=rule.message_vi,
            suggestion_vi=rule.suggestion_vi,
        )
    return None


def summarize_issues(issues: list[ValidationIssue]) -> ValidationSummary:
    summary = ValidationSummary()
    for issue in issues:
        setattr(summary, issue.severity, getattr(summary, issue.severity) + 1)
    return summary


def status_from_summary(summary: ValidationSummary) -> str:
    """Shared status rollup, reused by `validate_form` and by the AI-issue merge
    step in `app.form_ai_review` so both paths roll up the same way."""
    if summary.blocking_error:
        return "invalid"
    if summary.warning:
        return "valid_with_warnings"
    if summary.unable_to_verify:
        return "unable_to_validate"
    return "valid"


def validate_form(candidate: FormCandidate, values: dict) -> ValidationResult:
    issues = [issue for field in candidate.fields if (issue := _check_field(field, values.get(field.field_code))) is not None]
    issues += [issue for rule in candidate.cross_field_rules if (issue := _check_cross_field_rule(rule, values)) is not None]
    summary = summarize_issues(issues)
    return ValidationResult(
        validation_id=str(uuid4()),
        form_code=candidate.form_code,
        input_hash=canonical_input_hash(values),
        status=status_from_summary(summary),
        summary=summary,
        issues=issues,
        validated_at=datetime.now(UTC).isoformat(),
    )
