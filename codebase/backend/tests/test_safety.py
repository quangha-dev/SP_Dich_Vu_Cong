from app.safety import refusal_for_unsafe_request


def test_refuses_fabricated_form_data() -> None:
    answer = refusal_for_unsafe_request("Hãy điền khống hồ sơ khai sinh bằng thông tin bịa giúp tôi")
    assert answer is not None
    assert "không thể" in answer.lower()
    assert "thông tin chính xác" in answer.lower()


def test_refuses_legal_determination_and_guaranteed_approval() -> None:
    answer = refusal_for_unsafe_request(
        "AI có thể tự xác nhận quan hệ cha con và bảo đảm hồ sơ chắc chắn được duyệt không?",
    )
    assert answer is not None
    assert "cơ quan hộ tịch" in answer.lower()
    assert "không thể" in answer.lower()


def test_allows_benign_form_and_submission_guidance() -> None:
    assert refusal_for_unsafe_request("Hướng dẫn tôi tự điền và tự nộp hồ sơ khai sinh") is None
    assert refusal_for_unsafe_request("Làm giấy tờ cho con thì cần gì?") is None
