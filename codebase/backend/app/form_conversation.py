"""Bridges the deterministic chat pipeline to the isolated form-filling LLM path.

`maybe_fill_form` is the single integration point called from `main.py`'s
`chat_stream` handler, right after `ProcedurePipeline.ainvoke`. It only ever
overrides the deterministic reply when the conversation resolves to one of the
form-mapped procedures (via `resolve_form_code`) — for every other procedure it is
a no-op, so `ProcedurePipeline` itself needs no changes.
"""

from typing import Any

from app.config import Settings
from app.form_llm import fill_form
from app.form_validation import validate_field_updates
from app.procedure_catalog import normalize_text
from app.procedure_settings import FormMapping, ProcedureSettings
from app.request_quality import deterministic_request_quality
from app.schemas import AssistantReply
from app.safety import refusal_for_unsafe_request


def resolve_form_code(active_procedure_code: str | None, message: str, mappings: tuple[FormMapping, ...]) -> str | None:
    # Defense in depth: a procedure keyword alone must never be sufficient to
    # open a form when the named object is incompatible with that procedure.
    if deterministic_request_quality(message, mappings).blocked:
        return None
    if active_procedure_code:
        for mapping in mappings:
            if active_procedure_code in mapping.match_procedure_codes:
                return mapping.form_code
    normalized_message = normalize_text(message)
    for mapping in mappings:
        if any(normalize_text(keyword) in normalized_message for keyword in mapping.match_keywords):
            return mapping.form_code
    return None


async def maybe_fill_form(
    state: dict[str, Any],
    result: dict[str, Any],
    settings: Settings,
    procedure_settings: ProcedureSettings,
    messages: list[dict[str, str]],
) -> tuple[AssistantReply, dict[str, Any] | None]:
    """Returns (reply_to_use, form_patch_or_None). form_patch is {"form_code", "fields"}."""
    message = messages[-1]["content"]
    if refusal_for_unsafe_request(message):
        # The deterministic pipeline already produced the scoped refusal. Do
        # not let a form keyword (for example "khai sinh") override it.
        return result["reply"], None
    active_form_code = state.get("active_scenario_code")
    # An explicit keyword match against a *different* form in the new message always wins over
    # a sticky active form — otherwise, once a form is active, later messages naming a different
    # procedure (e.g. "đăng ký khai sinh" while active_scenario_code is still the construction
    # form) get silently ignored and the session stays stuck on the old form forever.
    keyword_match = resolve_form_code(None, message, procedure_settings.form_mappings)
    if keyword_match and keyword_match != active_form_code:
        form_code = keyword_match
    elif active_form_code in procedure_settings.form_candidates:
        form_code = active_form_code
    else:
        form_code = resolve_form_code(result.get("active_procedure_code"), message, procedure_settings.form_mappings)
    if form_code is None:
        return result["reply"], None

    candidate = procedure_settings.form_candidates[form_code]
    known_fields = state.get("form_draft", {}).get(form_code, {})
    form_reply = await fill_form(settings, messages[-6:], state.get("language_code", "vi"), candidate, known_fields)
    newly_extracted = {
        field_code: value
        for field_code, value in form_reply.extracted_fields.items()
        if value and candidate.field_by_code(field_code) is not None
    }
    accepted_fields: dict[str, str] = {}
    rejected_issues = []
    for field_code, value in newly_extracted.items():
        issues = validate_field_updates(candidate, {**known_fields, **accepted_fields}, {field_code: value})
        blocking_issues = [issue for issue in issues if issue.severity == "blocking_error"]
        if blocking_issues:
            rejected_issues.extend(blocking_issues)
        else:
            accepted_fields[field_code] = value
    merged_fields = {**known_fields, **accepted_fields}
    if rejected_issues:
        issue = rejected_issues[0]
        field = candidate.field_by_code(issue.field_code or "")
        label = field.label_vi.lower() if field else "thông tin này"
        guidance = f" {issue.suggestion_vi}" if issue.suggestion_vi else ""
        form_reply.answer = f"Thông tin vừa nhập chưa hợp lệ. {issue.message_vi}{guidance} Vui lòng nhập lại {label}."
        form_reply.quick_replies = list(field.validation.enum_values) if field and field.validation.enum_values else []
    new_reply = AssistantReply(intent="form_guidance", answer=form_reply.answer, quick_replies=form_reply.quick_replies)
    return new_reply, {
        "form_code": form_code,
        "fields": merged_fields,
        "accepted_field_codes": list(accepted_fields),
        "rejected_issues": [issue.model_dump() for issue in rejected_issues],
    }
