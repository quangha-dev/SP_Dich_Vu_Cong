import json
from pathlib import Path

import pytest
from fakeredis.aioredis import FakeRedis
from httpx import ASGITransport, AsyncClient

from app import form_export
from app.agent_runtime import record_tool_result
from app.config import Settings
from app.main import create_app

TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost:5432/test"

_DEV_FALLBACK_FONTS = (
    Path("/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/Library/Fonts/Arial Unicode.ttf"),
    Path("C:/Windows/Fonts/times.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("C:/Windows/Fonts/segoeui.ttf"),
)


def _available_font() -> Path | None:
    return next((path for path in _DEV_FALLBACK_FONTS if path.is_file()), None)


@pytest.fixture
def app():
    return create_app(
        Settings(llm_api_key="", llm_model="", environment="LOCAL", session_ttl_seconds=1800, database_url=TEST_DATABASE_URL),
        FakeRedis(decode_responses=True),
    )


VALID_BIRTH_VALUES = {
    "applicant_full_name": "Nguyễn Văn An",
    "relationship_to_child": "Cha",
    "child_full_name": "Nguyễn Thị Hồng Ánh",
    "child_birth_date": "2026-01-01",
    "child_gender": "Nữ",
    "child_ethnicity": "Kinh",
    "child_nationality": "Việt Nam",
    "child_birth_place": "Bệnh viện Phụ sản Hà Nội",
    "mother_full_name": "Trần Thị Bích",
    "copy_request_needed": "Không",
}


@pytest.mark.asyncio
async def test_cors_preflight_allows_put_for_draft_endpoint(app) -> None:
    """Regression test: browsers send a PUT preflight for the draft endpoint's
    Content-Type: application/json body; if "PUT" is missing from the CORS
    middleware's allow_methods, the browser silently blocks the real request
    with no server-side trace (httpx/TestClient calls don't enforce this, so
    only a real browser or an explicit OPTIONS check catches it)."""
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.options(
                "/api/v1/forms/BIRTH_REGISTRATION_FORM/draft",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "PUT",
                    "Access-Control-Request-Headers": "content-type",
                },
            )
    assert response.status_code == 200
    assert "PUT" in response.headers["access-control-allow-methods"]


@pytest.mark.asyncio
async def test_production_startup_requires_a_vietnamese_pdf_font(monkeypatch) -> None:
    def missing_font() -> None:
        raise form_export.ExportError(None, "vietnamese_font_missing")

    monkeypatch.setattr("app.main.ensure_vietnamese_font", missing_font)
    production_app = create_app(
        Settings(llm_api_key="", llm_model="", environment="PRODUCTION", database_url=TEST_DATABASE_URL),
        FakeRedis(decode_responses=True),
    )
    with pytest.raises(form_export.ExportError, match="vietnamese_font_missing"):
        async with production_app.router.lifespan_context(production_app):
            pass


@pytest.mark.asyncio
async def test_form_schema_returns_groups_and_fields(app) -> None:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/forms/BIRTH_REGISTRATION_FORM/schema")
    assert response.status_code == 200
    body = response.json()
    assert body["form_code"] == "BIRTH_REGISTRATION_FORM"
    assert any(field["field_code"] == "child_full_name" for field in body["fields"])


@pytest.mark.asyncio
async def test_unknown_form_code_is_404(app) -> None:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/forms/NOT_A_FORM/schema")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_draft_update_and_get_round_trip(app) -> None:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            put_response = await client.put("/api/v1/forms/BIRTH_REGISTRATION_FORM/draft", json={"fields": {"child_full_name": "Nguyễn Thị Hồng Ánh"}})
            assert put_response.status_code == 200
            assert put_response.json()["fields"]["child_full_name"] == "Nguyễn Thị Hồng Ánh"

            get_response = await client.get("/api/v1/forms/BIRTH_REGISTRATION_FORM/draft")
            assert get_response.status_code == 200
            assert get_response.json()["fields"]["child_full_name"] == "Nguyễn Thị Hồng Ánh"


@pytest.mark.asyncio
async def test_validate_reports_missing_required_fields(app) -> None:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.put("/api/v1/forms/BIRTH_REGISTRATION_FORM/draft", json={"fields": {"child_full_name": "Nguyễn Thị Hồng Ánh"}})
            response = await client.post("/api/v1/forms/BIRTH_REGISTRATION_FORM/validate")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "invalid"
    assert body["summary"]["blocking_error"] > 0


@pytest.mark.asyncio
async def test_long_agent_collection_can_validate_preview_pdf_and_reuse_result(app, monkeypatch) -> None:
    """A ten-field birth-registration chat used to consume the old 12-call
    workflow budget before the user could validate, causing the frontend to
    receive no server-issued validation id."""
    font_path = _available_font()
    if font_path is None:
        pytest.skip("no Unicode-complete TTF available on this machine to exercise the real render path")
    monkeypatch.setattr(form_export, "_FONT_CANDIDATES", (font_path,))
    monkeypatch.setattr(form_export, "_registered", False)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.put("/api/v1/forms/BIRTH_REGISTRATION_FORM/draft", json={"fields": VALID_BIRTH_VALUES})
            session_id = client.cookies.get("icivi_session")
            state = await app.state.store.get(session_id)
            history = record_tool_result([], "lookup_procedure", {"form_code": "BIRTH_REGISTRATION_FORM"})
            history = record_tool_result(history, "prepare_birth_registration", {"form_code": "BIRTH_REGISTRATION_FORM"})
            for index in range(10):
                history = record_tool_result(history, "collect_form_data", {"fields": {"step": index}})
            state["agent_workflow"] = {
                "form_code": "BIRTH_REGISTRATION_FORM",
                "status": "ready_for_review",
                "tool_history": history,
            }
            await app.state.store.save(session_id, state)

            first = await client.post("/api/v1/forms/BIRTH_REGISTRATION_FORM/validate")
            second = await client.post("/api/v1/forms/BIRTH_REGISTRATION_FORM/validate")
            preview = await client.post(
                "/api/v1/forms/BIRTH_REGISTRATION_FORM/exports/pdf",
                json={"validation_id": first.json()["validation_id"]},
            )

    assert first.status_code == 200
    assert first.json()["status"] == "valid"
    assert second.status_code == 200
    assert second.json()["validation_id"] == first.json()["validation_id"]
    assert preview.status_code == 200
    assert preview.content.startswith(b"%PDF-")


@pytest.mark.asyncio
async def test_export_rejects_stale_validation_id(app) -> None:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.put("/api/v1/forms/BIRTH_REGISTRATION_FORM/draft", json={"fields": VALID_BIRTH_VALUES})
            response = await client.post("/api/v1/forms/BIRTH_REGISTRATION_FORM/exports/pdf", json={"validation_id": "not-a-real-id"})
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_export_rejects_when_draft_changed_after_validation(app) -> None:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.put("/api/v1/forms/BIRTH_REGISTRATION_FORM/draft", json={"fields": VALID_BIRTH_VALUES})
            validation = (await client.post("/api/v1/forms/BIRTH_REGISTRATION_FORM/validate")).json()
            await client.put("/api/v1/forms/BIRTH_REGISTRATION_FORM/draft", json={"fields": {"child_full_name": "Đã sửa"}})
            response = await client.post("/api/v1/forms/BIRTH_REGISTRATION_FORM/exports/pdf", json={"validation_id": validation["validation_id"]})
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_export_rejects_blocking_errors(app) -> None:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.put("/api/v1/forms/BIRTH_REGISTRATION_FORM/draft", json={"fields": {"child_full_name": "Chỉ một trường"}})
            validation = (await client.post("/api/v1/forms/BIRTH_REGISTRATION_FORM/validate")).json()
            assert validation["status"] == "invalid"
            response = await client.post("/api/v1/forms/BIRTH_REGISTRATION_FORM/exports/pdf", json={"validation_id": validation["validation_id"]})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_full_happy_path_produces_a_pdf(app, monkeypatch) -> None:
    font_path = _available_font()
    if font_path is None:
        pytest.skip("no Unicode-complete TTF available on this machine to exercise the real render path")
    monkeypatch.setattr(form_export, "_FONT_CANDIDATES", (font_path,))
    monkeypatch.setattr(form_export, "_registered", False)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.put("/api/v1/forms/BIRTH_REGISTRATION_FORM/draft", json={"fields": VALID_BIRTH_VALUES})
            validation = (await client.post("/api/v1/forms/BIRTH_REGISTRATION_FORM/validate")).json()
            assert validation["status"] == "valid"
            response = await client.post("/api/v1/forms/BIRTH_REGISTRATION_FORM/exports/pdf", json={"validation_id": validation["validation_id"]})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:4] == b"%PDF"


@pytest.mark.asyncio
async def test_simulated_submission_requires_explicit_confirmation(app) -> None:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.put("/api/v1/forms/BIRTH_REGISTRATION_FORM/draft", json={"fields": VALID_BIRTH_VALUES})
            validation = (await client.post("/api/v1/forms/BIRTH_REGISTRATION_FORM/validate")).json()
            response = await client.post(
                "/api/v1/forms/BIRTH_REGISTRATION_FORM/submissions/simulate",
                json={"validation_id": validation["validation_id"], "confirmed": False},
            )
    assert response.status_code == 422
    assert response.json()["detail"] == "explicit_confirmation_required"


@pytest.mark.asyncio
async def test_simulated_submission_returns_clearly_labeled_demo_receipt(app) -> None:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.put("/api/v1/forms/BIRTH_REGISTRATION_FORM/draft", json={"fields": VALID_BIRTH_VALUES})
            validation = (await client.post("/api/v1/forms/BIRTH_REGISTRATION_FORM/validate")).json()
            approval = (await client.post(
                "/api/v1/forms/BIRTH_REGISTRATION_FORM/submissions/approval",
                json={"validation_id": validation["validation_id"]},
            )).json()
            assert "Nguyễn Văn An" not in json.dumps(approval, ensure_ascii=False)
            assert "Họ, chữ đệm, tên người yêu cầu" in approval["disclosed_fields"]
            response = await client.post(
                "/api/v1/forms/BIRTH_REGISTRATION_FORM/submissions/simulate",
                json={"validation_id": validation["validation_id"], "approval_id": approval["approval_id"], "confirmed": True},
            )
            receipt_in_session = response.json()
            artifact = await client.get(f"/api/v1/submissions/{receipt_in_session['submission_id']}/artifact.pdf")
            replay = await client.post(
                "/api/v1/forms/BIRTH_REGISTRATION_FORM/submissions/simulate",
                json={"validation_id": validation["validation_id"], "approval_id": approval["approval_id"], "confirmed": True},
            )
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other_session:
                cross_session_artifact = await other_session.get(f"/api/v1/submissions/{receipt_in_session['submission_id']}/artifact.pdf")
    assert response.status_code == 200
    receipt = response.json()
    assert receipt["status"] == "submitted_simulation"
    assert receipt["simulation"] is True
    assert receipt["official_submission"] is False
    assert receipt["receipt_code"].startswith("SPDVC-DEMO-")
    assert receipt["artifact_available"] is True
    assert receipt["delivery_destination"] == "SPDVC_DEMO_GATEWAY"
    assert receipt["pdf_size_bytes"] > 100
    assert "Nguyễn" not in json.dumps(receipt, ensure_ascii=False)
    assert artifact.status_code == 200 and artifact.content.startswith(b"%PDF-")
    assert replay.status_code == 200 and replay.json()["submission_id"] == receipt["submission_id"]
    assert cross_session_artifact.status_code == 404


@pytest.mark.asyncio
async def test_simulated_submission_rejects_draft_changed_after_validation(app) -> None:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.put("/api/v1/forms/BIRTH_REGISTRATION_FORM/draft", json={"fields": VALID_BIRTH_VALUES})
            validation = (await client.post("/api/v1/forms/BIRTH_REGISTRATION_FORM/validate")).json()
            await client.put("/api/v1/forms/BIRTH_REGISTRATION_FORM/draft", json={"fields": {"child_full_name": "Tên mới"}})
            response = await client.post(
                "/api/v1/forms/BIRTH_REGISTRATION_FORM/submissions/simulate",
                json={"validation_id": validation["validation_id"], "confirmed": True},
            )
    assert response.status_code == 409
    assert response.json()["detail"] == "draft_changed_since_validation"


class _FakeAiReviewResponse:
    status_code = 200
    headers = {"content-type": "application/json"}

    def __init__(self, content: str) -> None:
        self._content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"choices": [{"message": {"content": self._content}}]}


class _FakeAiReviewAsyncClient:
    reply_content: str = json.dumps({"issues": []})

    def __init__(self, *args, **kwargs) -> None:
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def post(self, url: str, json: dict, headers: dict) -> _FakeAiReviewResponse:
        return _FakeAiReviewResponse(_FakeAiReviewAsyncClient.reply_content)


@pytest.mark.asyncio
async def test_validate_endpoint_merges_ai_flagged_issue(monkeypatch) -> None:
    _FakeAiReviewAsyncClient.reply_content = json.dumps({
        "issues": [{
            "field_code": "child_birth_place",
            "issue_code": "IMPLAUSIBLE_BIRTH_PLACE",
            "severity": "warning",
            "message_vi": "Nơi sinh không giống một cơ sở y tế.",
            "suggestion_vi": None,
        }],
    })
    monkeypatch.setattr("app.form_ai_review.httpx.AsyncClient", _FakeAiReviewAsyncClient)
    ai_app = create_app(
        Settings(llm_api_key="test-key", llm_model="test-model", environment="LOCAL", session_ttl_seconds=1800, database_url=TEST_DATABASE_URL),
        FakeRedis(decode_responses=True),
    )
    async with ai_app.router.lifespan_context(ai_app):
        async with AsyncClient(transport=ASGITransport(app=ai_app), base_url="http://test") as client:
            await client.put("/api/v1/forms/BIRTH_REGISTRATION_FORM/draft", json={"fields": VALID_BIRTH_VALUES})
            response = await client.post("/api/v1/forms/BIRTH_REGISTRATION_FORM/validate")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "valid_with_warnings"
    assert any(issue["rule_code"] == "AI_IMPLAUSIBLE_BIRTH_PLACE" for issue in body["issues"])
