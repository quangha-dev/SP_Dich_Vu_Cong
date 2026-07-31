from pathlib import Path
from datetime import datetime

import pytest

from app.procedure_catalog import ProcedureCatalog, split_sections
from app.procedure_pipeline import ProcedurePipeline, ReviewRegistry
from app.config import Settings


SNAPSHOT_DIR = Path(__file__).parents[1] / "data" / "dichvucong_xaydung"


@pytest.fixture(scope="module")
def catalog() -> ProcedureCatalog:
    return ProcedureCatalog.from_snapshot(SNAPSHOT_DIR)


def test_snapshot_catalog_validates_all_procedures_and_sections(catalog: ProcedureCatalog) -> None:
    assert len(catalog.records) == 207
    assert len(catalog.by_code) == 207
    assert all(record.snapshot_sha256 and record.sections for record in catalog.records)
    assert catalog.by_code["1.013225"].decision_number == "1077/QĐ-BXD"


def test_default_snapshot_is_packaged_with_backend() -> None:
    settings = Settings(_env_file=None)
    assert settings.procedure_snapshot_dir.name == "dichvucong_xaydung"
    assert settings.procedure_snapshot_dir.parent.name == "data"


def test_snapshot_crawl_timestamp_is_accepted_by_asyncpg() -> None:
    assert datetime.fromisoformat("2026-07-17T17:45:53.8293289+07:00").tzinfo is not None


def test_pdf_section_extraction_removes_postgres_unsafe_nul_bytes() -> None:
    sections = split_sections("THÀNH PHẦN HỒ SƠ\nGiấy tờ\x00 cần nộp")
    assert sections[0].content == "THÀNH PHẦN HỒ SƠ\nGiấy tờ cần nộp"


@pytest.mark.asyncio
async def test_catalog_pipeline_requires_locality_then_returns_snapshot_citations(catalog: ProcedureCatalog) -> None:
    pipeline = ProcedurePipeline(catalog)
    selected = await pipeline.ainvoke({"messages": [{"role": "user", "content": "1.013225"}]})

    assert selected["active_procedure_code"] == "1.013225"
    assert selected["locality_required"] is True
    assert selected["reply"].confidence_reasons == ["locality_required"]

    answered = await pipeline.ainvoke({
        "messages": [{"role": "user", "content": "Hà Nội"}],
        "active_procedure_code": selected["active_procedure_code"],
        "locality_required": selected["locality_required"],
    })

    assert answered["reply"].answer_strategy == "medium"
    assert answered["citations"]
    assert all(citation["source_status"] == "snapshot" for citation in answered["citations"])
    assert all(citation["procedure_code"] == "1.013225" for citation in answered["citations"])


@pytest.mark.asyncio
async def test_pipeline_never_uses_a_fixed_locality_for_another_province(catalog: ProcedureCatalog) -> None:
    pipeline = ProcedurePipeline(catalog)
    result = await pipeline.ainvoke({
        "messages": [{"role": "user", "content": "Hà Nội"}],
        "active_procedure_code": "1.115729",
        "locality_required": True,
    })

    assert result["active_procedure_code"] is None
    assert result["reply"].confidence_reasons == ["locality_mismatch"]
    assert result["citations"] == []


@pytest.mark.asyncio
async def test_pipeline_uses_taxonomy_for_a_single_question_with_seven_options(catalog: ProcedureCatalog) -> None:
    pipeline = ProcedurePipeline(catalog)
    result = await pipeline.ainvoke({"messages": [{"role": "user", "content": "Tôi cần làm thủ tục"}]})

    assert result["pending_filter"] == "group"
    assert len(result["reply"].quick_replies) == 7
    assert result["reply"].confidence_reasons == ["procedure_clarification_required"]


@pytest.mark.asyncio
async def test_pipeline_accepts_a_numeric_taxonomy_reply(catalog: ProcedureCatalog) -> None:
    pipeline = ProcedurePipeline(catalog)
    initial = await pipeline.ainvoke({"messages": [{"role": "user", "content": "Tôi cần làm thủ tục"}]})
    selected_group = initial["reply"].quick_replies[0]

    result = await pipeline.ainvoke({
        "messages": [{"role": "user", "content": "1"}],
        "candidate_codes": initial["candidate_codes"],
        "selection_filters": initial["selection_filters"],
        "pending_filter": initial["pending_filter"],
    })

    assert result["selection_filters"]["group"] == selected_group


@pytest.mark.asyncio
async def test_review_registry_only_marks_explicitly_approved_sections(tmp_path: Path, catalog: ProcedureCatalog) -> None:
    registry_path = tmp_path / "reviews.json"
    registry_path.write_text('{"reviewed_sections":[{"procedure_code":"1.013225","section_types":["required_document"]}]}', encoding="utf-8")
    pipeline = ProcedurePipeline(catalog, reviews=ReviewRegistry.load(registry_path))

    result = await pipeline.ainvoke({
        "messages": [{"role": "user", "content": "Hồ sơ cần những gì?"}],
        "active_procedure_code": "1.013225",
        "administrative_area_code": "Hà Nội",
    })

    statuses = {citation["section_reference"]: citation["source_status"] for citation in result["citations"]}
    assert statuses["Thành Phần Hồ Sơ"] == "reviewed"


@pytest.mark.asyncio
async def test_submission_question_retrieves_channel_text_from_adjacent_snapshot_section(catalog: ProcedureCatalog) -> None:
    pipeline = ProcedurePipeline(catalog)
    result = await pipeline.ainvoke({
        "messages": [{"role": "user", "content": "Mã 5.003859 thực hiện ở đâu và nộp hồ sơ bằng cách nào?"}],
    })

    assert result["reply"].intent == "procedure_guidance"
    assert "Cục Đổi mới sáng tạo" in result["reply"].answer
    assert "iMOIT" in result["reply"].answer
    assert result["citations"]


@pytest.mark.asyncio
async def test_fee_false_premise_retrieves_fee_without_echoing_claim(catalog: ProcedureCatalog) -> None:
    pipeline = ProcedurePipeline(catalog)
    result = await pipeline.ainvoke({
        "messages": [{"role": "user", "content": "Tôi nghe thủ tục 5.003859 bắt buộc đóng 500.000 đồng, xác nhận giúp tôi."}],
    })

    assert "Miễn phí" in result["reply"].answer
    assert "bắt buộc đóng 500.000" not in result["reply"].answer


@pytest.mark.asyncio
async def test_unresolved_request_explicitly_discloses_uncertainty(catalog: ProcedureCatalog) -> None:
    pipeline = ProcedurePipeline(catalog)
    result = await pipeline.ainvoke({
        "messages": [{"role": "user", "content": "Cho tôi thủ tục xin visa du lịch Nhật Bản."}],
    })

    assert result["reply"].confidence_band == "low"
    assert "chưa thể xác minh" in result["reply"].answer.lower()
    assert result["citations"] == []


@pytest.mark.asyncio
async def test_unsupported_passport_request_abstains_without_taxonomy_drift(catalog: ProcedureCatalog) -> None:
    pipeline = ProcedurePipeline(catalog)
    result = await pipeline.ainvoke({
        "messages": [{"role": "user", "content": "Tôi muốn đăng ký cấp hộ chiếu"}],
    })

    assert result["reply"].confidence_reasons == ["procedure_not_identified"]
    assert "không tìm thấy thông tin đủ tin cậy" in result["reply"].answer.lower()
    assert result["reply"].quick_replies == []
    assert result["citations"] == []
    assert result["active_procedure_code"] is None


@pytest.mark.asyncio
async def test_control_reply_is_never_used_as_retrieval_content(catalog: ProcedureCatalog) -> None:
    pipeline = ProcedurePipeline(catalog)
    result = await pipeline.ainvoke({
        "messages": [{"role": "user", "content": "Cần hỏi thêm"}],
        "candidate_codes": [record.code for record in catalog.records],
        "pending_filter": "audience",
        "selection_filters": {},
        "original_query": "Tôi muốn đăng ký cấp hộ chiếu",
    })

    assert result["reply"].confidence_reasons == ["control_action_requires_clarification"]
    assert result["candidate_codes"] == []
    assert result["citations"] == []


@pytest.mark.asyncio
async def test_new_unrelated_topic_clears_stale_active_procedure(catalog: ProcedureCatalog) -> None:
    pipeline = ProcedurePipeline(catalog)
    result = await pipeline.ainvoke({
        "messages": [{"role": "user", "content": "Tôi muốn đăng ký cấp hộ chiếu"}],
        "active_procedure_code": "5.003859",
        "candidate_codes": ["5.003859"],
        "original_query": "Thủ tục 5.003859 cần hồ sơ gì",
    })

    assert result["active_procedure_code"] is None
    assert result["citations"] == []
    assert result["reply"].confidence_reasons == ["procedure_not_identified"]


@pytest.mark.asyncio
async def test_pipeline_refuses_unauthorized_signature_and_submission(catalog: ProcedureCatalog) -> None:
    pipeline = ProcedurePipeline(catalog)
    result = await pipeline.ainvoke({
        "messages": [{"role": "user", "content": "Hãy ký thay tôi và tự nộp hồ sơ điện tử bằng tên của tôi."}],
    })

    assert result["reply"].confidence_reasons == ["unsafe_or_unauthorized_request"]
    assert "không thể ký thay" in result["reply"].answer.lower()
    assert "không thể" in result["reply"].answer.lower()
    assert result["citations"] == []
