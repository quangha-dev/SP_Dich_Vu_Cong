"""Deterministic safety boundary for actions the prototype cannot perform."""

from __future__ import annotations

import re

from app.procedure_catalog import normalize_text


def _contains_phrase(text: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text) is not None


def refusal_for_unsafe_request(message: str) -> str | None:
    """Return a scoped refusal for clear fabrication, impersonation, or legal-decision requests."""

    normalized = normalize_text(message)

    fabrication_markers = (
        "dien khong",
        "thong tin bia",
        "thong tin gia",
        "gia mao",
        "lam gia",
    )
    if any(_contains_phrase(normalized, marker) for marker in fabrication_markers):
        return (
            "Tôi không thể hỗ trợ điền khống, tạo hoặc gửi hồ sơ bằng thông tin bịa/giả. "
            "Bạn cần cung cấp thông tin chính xác; tôi chỉ có thể giúp kiểm tra và hoàn thiện bản nháp để bạn tự xác nhận."
        )

    asks_to_sign_for_user = "ky thay" in normalized or "ky xac nhan giup" in normalized
    asks_to_submit_for_user = (
        "nop thay" in normalized
        or (
            "tu nop ho so" in normalized
            and "huong dan" not in normalized
            and ("hay" in normalized or "giup toi" in normalized or "bang ten cua toi" in normalized)
        )
        or ("nop ho so" in normalized and "bang ten cua toi" in normalized)
    )
    if asks_to_sign_for_user or asks_to_submit_for_user:
        return (
            "Tôi không thể ký thay, mạo danh hoặc tự nộp hồ sơ điện tử cho bạn. "
            "Tôi chỉ có thể hướng dẫn và chuẩn bị bản nháp; bạn phải tự kiểm tra, ký/xác nhận và nộp qua kênh chính thức."
        )

    asks_for_legal_determination = (
        ("tu xac nhan" in normalized and ("quan he" in normalized or "du dieu kien" in normalized))
        or ("bao dam" in normalized and ("duoc duyet" in normalized or "chac chan" in normalized))
    )
    if asks_for_legal_determination:
        return (
            "Tôi không thể tự xác nhận quan hệ pháp lý, quyết định điều kiện hoặc bảo đảm hồ sơ chắc chắn được duyệt. "
            "Bạn cần xác minh với cơ quan hộ tịch/cơ quan có thẩm quyền hoặc nguồn chính thức; tôi chỉ cung cấp hướng dẫn có căn cứ."
        )

    return None
