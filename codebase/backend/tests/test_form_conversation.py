import pytest

from app.config import Settings
from app.form_conversation import maybe_fill_form, resolve_form_code
from app.procedure_settings import load_procedure_settings
from app.schemas import AssistantReply
from app.form_llm import FormFillingReply

SETTINGS = load_procedure_settings()


def test_resolve_form_code_by_keyword() -> None:
    assert resolve_form_code(None, "Tôi muốn đăng ký khai sinh cho con", SETTINGS.form_mappings) == "BIRTH_REGISTRATION_FORM"
    assert resolve_form_code(None, "làm sao đăng ký thường trú", SETTINGS.form_mappings) == "PERMANENT_RESIDENCE_CT01_FORM"
    assert resolve_form_code(None, "xin giấy phép xây dựng nhà ở riêng lẻ", SETTINGS.form_mappings) == "CONSTRUCTION_PERMIT_REQUEST_FORM"


def test_resolve_form_code_by_procedure_code_takes_priority() -> None:
    assert resolve_form_code("1.013225", "không liên quan gì cả", SETTINGS.form_mappings) == "CONSTRUCTION_PERMIT_REQUEST_FORM"


def test_resolve_form_code_returns_none_for_unrelated_message() -> None:
    assert resolve_form_code(None, "thủ tục cấp phép khai thác cát", SETTINGS.form_mappings) is None


def test_resolve_form_code_does_not_route_illogical_keyword_match() -> None:
    assert resolve_form_code(
        None, "tôi muốn đăng kí khai sinh ngôn ngữ cho LLM", SETTINGS.form_mappings,
    ) is None
    assert resolve_form_code(
        "1.013225", "tôi muốn đăng kí khai sinh ngôn ngữ cho LLM", SETTINGS.form_mappings,
    ) is None


@pytest.mark.asyncio
async def test_maybe_fill_form_is_noop_for_unrelated_procedure() -> None:
    state = {"active_scenario_code": None, "form_draft": {}, "language_code": "vi"}
    result = {"reply": AssistantReply(intent="procedure_guidance", answer="ok", quick_replies=[]), "active_procedure_code": None}
    messages = [{"role": "user", "content": "hỏi về thủ tục khác không liên quan"}]
    reply, patch = await maybe_fill_form(state, result, Settings(), SETTINGS, messages)
    assert reply is result["reply"]
    assert patch is None


@pytest.mark.asyncio
async def test_maybe_fill_form_uses_mock_reply_without_llm_key() -> None:
    state = {"active_scenario_code": None, "form_draft": {}, "language_code": "vi"}
    result = {"reply": AssistantReply(intent="general", answer="ok", quick_replies=[]), "active_procedure_code": None}
    messages = [{"role": "user", "content": "tôi muốn đăng ký khai sinh cho bé"}]
    reply, patch = await maybe_fill_form(state, result, Settings(llm_api_key="", llm_model=""), SETTINGS, messages)
    assert reply.intent == "form_guidance"
    assert patch is not None
    assert patch["form_code"] == "BIRTH_REGISTRATION_FORM"


@pytest.mark.asyncio
async def test_maybe_fill_form_switches_away_from_a_stuck_sticky_form() -> None:
    """Regression test for a real stuck session: once active_scenario_code was set to the
    construction form on an earlier turn, a later message explicitly naming a different
    procedure ("đăng ký khai sinh") must switch forms, not silently stay stuck."""
    state = {
        "active_scenario_code": "CONSTRUCTION_PERMIT_REQUEST_FORM",
        "form_draft": {"CONSTRUCTION_PERMIT_REQUEST_FORM": {"owner_name": "Nguyễn Văn A"}},
        "language_code": "vi",
    }
    result = {"reply": AssistantReply(intent="general", answer="ok", quick_replies=[]), "active_procedure_code": "1.007754"}
    messages = [{"role": "user", "content": "Tôi muốn đăng ký khai sinh cho bé"}]
    reply, patch = await maybe_fill_form(state, result, Settings(llm_api_key="", llm_model=""), SETTINGS, messages)
    assert reply.intent == "form_guidance"
    assert patch is not None
    assert patch["form_code"] == "BIRTH_REGISTRATION_FORM"


@pytest.mark.asyncio
async def test_maybe_fill_form_keeps_active_form_for_plain_slot_answer() -> None:
    """A bare slot-filling answer with no keyword overlap must not reset the active form."""
    state = {
        "active_scenario_code": "BIRTH_REGISTRATION_FORM",
        "form_draft": {"BIRTH_REGISTRATION_FORM": {}},
        "language_code": "vi",
    }
    result = {"reply": AssistantReply(intent="general", answer="ok", quick_replies=[]), "active_procedure_code": None}
    messages = [{"role": "user", "content": "Nguyễn Văn An"}]
    _reply, patch = await maybe_fill_form(state, result, Settings(llm_api_key="", llm_model=""), SETTINGS, messages)
    assert patch is not None
    assert patch["form_code"] == "BIRTH_REGISTRATION_FORM"


@pytest.mark.asyncio
async def test_maybe_fill_form_does_not_false_switch_on_generic_residence_answer() -> None:
    """Answering the birth form's own "residence" field ("cư trú tại Hà Nội") must not
    falsely trigger a switch to the CT01 residence form after tightening its keywords."""
    state = {
        "active_scenario_code": "BIRTH_REGISTRATION_FORM",
        "form_draft": {"BIRTH_REGISTRATION_FORM": {}},
        "language_code": "vi",
    }
    result = {"reply": AssistantReply(intent="general", answer="ok", quick_replies=[]), "active_procedure_code": None}
    messages = [{"role": "user", "content": "cư trú tại Hà Nội"}]
    _reply, patch = await maybe_fill_form(state, result, Settings(llm_api_key="", llm_model=""), SETTINGS, messages)
    assert patch is not None
    assert patch["form_code"] == "BIRTH_REGISTRATION_FORM"


@pytest.mark.asyncio
async def test_maybe_fill_form_does_not_override_a_safety_refusal() -> None:
    state = {"active_scenario_code": None, "form_draft": {}, "language_code": "vi"}
    refusal = AssistantReply(
        intent="general",
        answer="Tôi không thể hỗ trợ điền khống bằng thông tin giả.",
        quick_replies=[],
        confidence_score=0.2,
        confidence_band="low",
    )
    result = {"reply": refusal, "active_procedure_code": None}
    messages = [{"role": "user", "content": "Hãy điền khống và gửi hồ sơ khai sinh bằng thông tin bịa giúp tôi."}]

    reply, patch = await maybe_fill_form(state, result, Settings(llm_api_key="", llm_model=""), SETTINGS, messages)

    assert reply is refusal
    assert patch is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field_code", "value", "issue_code"),
    [
        ("applicant_full_name", "abc xyz aaa", "NAME_PLACEHOLDER_BLOCKED"),
        ("relationship_to_child", "ông cố - con", "RELATIONSHIP_CONTRADICTORY"),
        ("child_full_name", "xxx zbz zbzz", "NAME_PLACEHOLDER_BLOCKED"),
        ("child_birth_date", "9999-99-99", "FIELD_DATE_UNPARSEABLE"),
    ],
)
async def test_agent_rejects_invalid_extracted_slot_before_saving(monkeypatch, field_code: str, value: str, issue_code: str) -> None:
    async def fake_fill_form(*_args, **_kwargs) -> FormFillingReply:
        return FormFillingReply(answer="Tiếp tục", extracted_fields={field_code: value})

    monkeypatch.setattr("app.form_conversation.fill_form", fake_fill_form)
    state = {"active_scenario_code": "BIRTH_REGISTRATION_FORM", "form_draft": {}, "language_code": "vi"}
    result = {"reply": AssistantReply(intent="general", answer="ok"), "active_procedure_code": None}
    reply, patch = await maybe_fill_form(
        state, result, Settings(llm_api_key="", llm_model=""), SETTINGS,
        [{"role": "user", "content": value}],
    )

    assert patch is not None
    assert field_code not in patch["fields"]
    assert patch["rejected_issues"][0]["issue_code"] == issue_code
    assert "Vui lòng nhập lại" in reply.answer
