import pytest

from app.config import Settings
from app.procedure_settings import load_procedure_settings
from app.request_quality import assess_request_quality, deterministic_request_quality


MAPPINGS = load_procedure_settings().form_mappings


@pytest.mark.parametrize("message", [
    "tôi muốn đăng kí khai sinh ngôn ngữ cho LLM",
    "đăng ký khai sinh cho chatbot",
    "đăng ký thường trú cho API",
    "xin giấy phép xây dựng cho robot",
])
def test_deterministic_gate_rejects_impossible_procedure_objects(message: str) -> None:
    result = deterministic_request_quality(message, MAPPINGS)
    assert result.status == "reject"
    assert result.reason_code == "procedure_object_mismatch"


@pytest.mark.parametrize("message", [
    "Tôi muốn đăng ký khai sinh cho bé",
    "Tôi muốn dùng chatbot để hỏi cách đăng ký khai sinh cho con",
    "Đăng ký thường trú cho gia đình tôi",
    "Xin giấy phép xây dựng nhà ở riêng lẻ",
])
def test_deterministic_gate_allows_coherent_requests(message: str) -> None:
    assert deterministic_request_quality(message, MAPPINGS).status == "pass"


def test_deterministic_gate_requires_one_procedure_at_a_time() -> None:
    result = deterministic_request_quality(
        "Tôi muốn đăng ký khai sinh và xin giấy phép xây dựng", MAPPINGS,
    )
    assert result.status == "clarify"
    assert result.reason_code == "multiple_procedures"


@pytest.mark.asyncio
async def test_slot_answer_bypasses_llm_quality_review() -> None:
    settings = Settings(llm_api_key="configured-but-must-not-be-used", llm_model="test-model")
    result = await assess_request_quality(
        settings, "Nguyễn Văn An", MAPPINGS,
        active_form_code="BIRTH_REGISTRATION_FORM", slot_answer=True,
    )
    assert result.status == "pass"


@pytest.mark.asyncio
async def test_clear_rag_question_is_not_suppressed_by_quality_model() -> None:
    settings = Settings(llm_api_key="configured-but-must-not-be-used", llm_model="test-model")
    result = await assess_request_quality(
        settings,
        "Thủ tục 5.003859 cần hồ sơ gì và thời hạn bao lâu?",
        MAPPINGS,
    )
    assert result.status == "pass"
    assert result.source == "deterministic"
