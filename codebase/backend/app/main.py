import asyncio
import base64
import hashlib
import json
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Cookie, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from redis.asyncio import Redis
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from app.config import Settings, get_settings
from app.agent_runtime import (
    AgentLoopStopped,
    assess_prompt_injection,
    build_agent_plan,
    normalize_untrusted_text,
    record_tool_result,
    redact_known_secrets,
)
from app.db import create_database_engine
from app.form_ai_review import ai_review_form, merge_ai_issues
from app.form_conversation import maybe_fill_form
from app.form_export import ExportError, ensure_vietnamese_font, render_export
from app.form_validation import canonical_input_hash, validate_form
from app.logging_config import configure_logging
from app.procedure_catalog import load_catalog
from app.procedure_pipeline import ProcedurePipeline, ReviewRegistry
from app.procedure_embeddings import ProcedureEmbeddingClient
from app.procedure_rag import ProcedureRagService
from app.procedure_settings import get_procedure_settings
from app.request_quality import assess_request_quality, request_quality_message
from app.schemas import (
    AssistantReply,
    ChatRequest,
    FormDraftResponse,
    FormDraftUpdateRequest,
    FormExportRequest,
    FormFieldSchema,
    FormGroupSchema,
    FormSchemaResponse,
    SimulatedSubmissionRequest,
    SimulatedSubmissionResponse,
    SubmissionApprovalRequest,
    SubmissionApprovalResponse,
    ValidationResult,
    VoiceStatusResponse,
    VoiceTranscriptResponse,
)
from app.session_store import SessionStore
from app.submission_simulation import (
    SubmissionSimulationError,
    create_submission_approval,
    create_simulated_submission,
    is_submission_simulation_request,
)
from app.translation import TranslationError, TranslationService, VIETNAMESE
from voice_ai.speech_to_text import SpeechToTextProcessor

logger = logging.getLogger(__name__)

MAX_VOICE_UPLOAD_BYTES = 10 * 1024 * 1024
VOICE_CLIENT_ERRORS = {
    "audio_decode_failed",
    "audio_decode_timeout",
    "audio_empty",
    "audio_too_long",
    "transcript_empty",
}


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def session_hash(session_id: str) -> str:
    return hashlib.sha256(session_id.encode()).hexdigest()[:10]


def create_app(settings: Settings | None = None, redis_client: Redis | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging()
        if settings.environment == "PRODUCTION":
            ensure_vietnamese_font()
        app.state.redis = redis_client or Redis.from_url(settings.redis_url, decode_responses=True)
        app.state.store = SessionStore(app.state.redis, settings.session_ttl_seconds)
        app.state.translation_service = TranslationService(settings)
        app.state.speech_to_text = SpeechToTextProcessor()
        if not app.state.speech_to_text.preflight():
            logger.warning(
                "voice_stt_unavailable reason=%s",
                app.state.speech_to_text.unavailable_reason,
            )
        app.state.database = create_database_engine(settings)
        procedure_settings = get_procedure_settings()
        catalog = load_catalog(str(settings.procedure_snapshot_dir), str(settings.procedure_catalog_path) if settings.procedure_catalog_path else None)
        app.state.procedure_pipeline = ProcedurePipeline(
            catalog,
            settings.retrieval_limit,
            ReviewRegistry.load(settings.procedure_review_registry_path),
            ProcedureRagService(app.state.database, ProcedureEmbeddingClient(settings), settings.retrieval_limit),
            procedure_settings,
        )
        logger.info("procedure_snapshot_loaded procedure_count=%d crawled_at=%s", len(catalog.records), catalog.crawled_at)
        yield
        await app.state.database.dispose()
        if redis_client is None:
            await app.state.redis.aclose()

    app = FastAPI(title="ICIVI MVP", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.cors_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )

    def set_session_cookie(response: Response, session_id: str) -> None:
        response.set_cookie(
            key=settings.session_cookie_name,
            value=session_id,
            httponly=True,
            samesite="lax",
            secure=settings.session_cookie_secure,
            max_age=settings.session_ttl_seconds,
            path="/",
        )

    async def ensure_session(session_id: str | None) -> tuple[str, dict, bool]:
        state = await app.state.store.get(session_id) if session_id else None
        if state is not None and session_id is not None:
            return session_id, state, False
        new_session_id = await app.state.store.create()
        return new_session_id, await app.state.store.get(new_session_id) or {}, True

    @app.get("/health")
    async def health() -> dict[str, str]:
        await app.state.redis.ping()
        return {"status": "ok"}

    @app.get("/api/v1/voice/status", response_model=VoiceStatusResponse)
    async def voice_status() -> VoiceStatusResponse:
        return VoiceStatusResponse(available=app.state.speech_to_text.preflight())

    @app.post("/api/v1/voice/transcribe", response_model=VoiceTranscriptResponse)
    async def transcribe_voice(file: UploadFile = File(...)) -> VoiceTranscriptResponse:
        processor = app.state.speech_to_text
        if not processor.preflight():
            raise HTTPException(status_code=503, detail="voice_unavailable")

        started = time.perf_counter()
        raw_audio = await file.read(MAX_VOICE_UPLOAD_BYTES + 1)
        await file.close()
        if len(raw_audio) > MAX_VOICE_UPLOAD_BYTES:
            logger.warning(
                "voice_transcription_rejected error_code=audio_too_large bytes=%d",
                len(raw_audio),
            )
            raise HTTPException(status_code=413, detail="audio_too_large")

        try:
            transcript = await run_in_threadpool(processor.transcribe, raw_audio)
        except RuntimeError as exc:
            error_code = str(exc)
            latency_ms = int((time.perf_counter() - started) * 1000)
            logger.warning(
                "voice_transcription_failed error_code=%s bytes=%d latency_ms=%d",
                error_code,
                len(raw_audio),
                latency_ms,
            )
            if error_code in {"ffmpeg_unavailable", "stt_unavailable"}:
                raise HTTPException(status_code=503, detail="voice_unavailable") from exc
            if error_code in VOICE_CLIENT_ERRORS:
                raise HTTPException(status_code=422, detail=error_code) from exc
            raise

        logger.info(
            "voice_transcription_complete bytes=%d transcript_chars=%d latency_ms=%d",
            len(raw_audio),
            len(transcript),
            int((time.perf_counter() - started) * 1000),
        )
        return VoiceTranscriptResponse(text=transcript)

    @app.post("/api/v1/sessions", status_code=204)
    async def create_session(session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name)) -> Response:
        response = Response(status_code=204)
        current_session_id, _, is_new = await ensure_session(session_id)
        if is_new:
            set_session_cookie(response, current_session_id)
        return response

    @app.delete("/api/v1/sessions/current", status_code=204)
    async def delete_session(session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name)) -> Response:
        response = Response(status_code=204)
        if session_id:
            await app.state.store.delete(session_id)
        response.delete_cookie(settings.session_cookie_name, path="/")
        return response

    @app.post("/api/v1/chat/stream")
    async def chat_stream(chat_request: ChatRequest, http_request: Request, session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name)):
        if len(chat_request.message) > settings.max_message_length:
            raise HTTPException(status_code=422, detail="Message exceeds configured length")
        current_session_id, state, is_new = await ensure_session(session_id)
        request_id = http_request.headers.get("x-request-id", "local")

        async def events() -> AsyncIterator[str]:
            started = time.perf_counter()
            try:
                needs_translation = chat_request.language_code != VIETNAMESE
                translation_consent = chat_request.translation_consent or state.get("translation_consent", False)
                has_trusted_context = bool(state.get("messages"))
                preflight_injection = assess_prompt_injection(
                    chat_request.message,
                    has_trusted_context=has_trusted_context,
                )
                if preflight_injection.blocked:
                    # Do not send an obvious attack to the translation provider.
                    canonical_message = normalize_untrusted_text(chat_request.message)
                    injection = preflight_injection
                else:
                    if needs_translation and not translation_consent:
                        yield sse("translation.consent_required", {"provider": settings.translation_provider_name})
                        return
                    canonical_message = await app.state.translation_service.to_vietnamese(
                        chat_request.message, chat_request.language_code,
                    )
                    injection = assess_prompt_injection(
                        canonical_message,
                        has_trusted_context=has_trusted_context,
                    )
                normalized_message = normalize_untrusted_text(canonical_message).casefold()
                clarification_choices = {
                    "hỏi thông tin thủ tục": "Tôi muốn hỏi thông tin về thủ tục này.",
                    "chuẩn bị hồ sơ": "Tôi muốn chuẩn bị hồ sơ cho thủ tục này.",
                }
                clarification_intent = clarification_choices.get(normalized_message)
                pending_clarification = state.get("pending_clarification_request")
                resumed_clarification = bool(clarification_intent and pending_clarification)
                if resumed_clarification:
                    canonical_message = f"{pending_clarification}\n{clarification_intent}"
                    normalized_message = normalize_untrusted_text(canonical_message).casefold()
                    state["pending_clarification_request"] = None
                repeated_user_message = normalized_message == state.get("last_user_message_normalized")
                if injection.blocked:
                    answer = (
                        "Yêu cầu bất thường này đã lặp lại và tiếp tục bị chặn. Không có tool, quyền hay thao tác phê duyệt nào được thực thi."
                        if repeated_user_message else
                        "Yêu cầu này có dấu hiệu thay đổi quy tắc, tự cấp quyền, giả mạo thẩm quyền, lấy thông tin bảo mật hoặc bỏ qua xác nhận. "
                        "Tôi đã chặn ngay lượt này; không có tool hay quyền nào được thực thi. Bạn vẫn có thể hỏi thủ tục bằng yêu cầu thông thường."
                    )
                    blocked_state = {
                        **state,
                        # Raw attack text is quarantined and never appended to the
                        # model-visible conversation on later turns.
                        "security_events": [
                            *state.get("security_events", []),
                            {
                                "input_hash": hashlib.sha256(canonical_message.encode("utf-8")).hexdigest(),
                                "risk_score": injection.risk_score,
                                "reasons": injection.reasons,
                            },
                        ][-10:],
                        "last_user_message_normalized": normalized_message,
                        "security_event_count": int(state.get("security_event_count", 0)) + 1,
                    }
                    await app.state.store.save(current_session_id, blocked_state)
                    for word in answer.split(" "):
                        yield sse("message.delta", {"text": f"{word} "})
                    yield sse("security.blocked", {"risk_score": injection.risk_score, "reasons": injection.reasons})
                    yield sse("message.complete", {
                        "intent": "out_of_scope", "quick_replies": ["Hỏi thông tin thủ tục", "Bắt đầu lại"], "citations": [],
                        "answer_strategy": "high", "confidence_score": 1, "confidence_band": "high",
                        "confidence_reasons": ["Deterministic prompt-injection policy"], "external_search_used": False,
                        "external_search_consent_required": False, "form_code": None, "translation_used": needs_translation,
                    })
                    return

                current_workflow = state.get("agent_workflow") or {}
                mode_choice = any(value in normalized_message for value in (
                    "điền từng bước", "cùng agent", "mở biểu mẫu", "điền trên biểu mẫu",
                ))
                slot_answer = bool(
                    current_workflow.get("status") in {"collecting", "ready_for_review"}
                    and not mode_choice
                )
                quality = await assess_request_quality(
                    settings,
                    canonical_message,
                    app.state.procedure_pipeline.procedure_settings.form_mappings,
                    active_form_code=state.get("active_scenario_code"),
                    slot_answer=slot_answer or mode_choice or repeated_user_message or resumed_clarification,
                )
                if quality.blocked:
                    answer, quick_replies = request_quality_message(quality)
                    quality_state = {
                        **state,
                        # Invalid content is quarantined just like an injection:
                        # keep an auditable hash/reason, never feed raw text back
                        # into the model-visible history on later turns.
                        "request_quality_events": [
                            *state.get("request_quality_events", []),
                            {
                                "input_hash": hashlib.sha256(canonical_message.encode("utf-8")).hexdigest(),
                                "status": quality.status,
                                "reason_code": quality.reason_code,
                                "source": quality.source,
                            },
                        ][-10:],
                        "last_user_message_normalized": normalized_message,
                        "pending_clarification_request": (
                            canonical_message if quality.status == "clarify" else None
                        ),
                    }
                    await app.state.store.save(current_session_id, quality_state)
                    for word in answer.split(" "):
                        yield sse("message.delta", {"text": f"{word} "})
                    yield sse("request.rejected", {
                        "status": quality.status,
                        "reason_code": quality.reason_code,
                    })
                    yield sse("message.complete", {
                        "intent": "out_of_scope" if quality.status == "reject" else "general",
                        "quick_replies": quick_replies,
                        "citations": [],
                        "answer_strategy": "high",
                        "confidence_score": 1,
                        "confidence_band": "high",
                        "confidence_reasons": [f"Pre-routing coherence gate: {quality.reason_code}"],
                        "external_search_used": False,
                        "external_search_consent_required": False,
                        "form_code": None,
                        "translation_used": needs_translation,
                    })
                    return

                workflow = state.get("agent_workflow") or {}
                repeated_agent_slot = bool(
                    workflow.get("status") == "collecting" and workflow.get("mode") == "agent_chat"
                )
                if repeated_user_message and not repeated_agent_slot:
                    answer = (
                        "Bạn vừa gửi lại đúng nội dung của lượt trước. Tôi không chạy lại Agent hoặc tool để tránh lặp vô hạn. "
                        "Hãy cung cấp thông tin mới, chọn một hướng đang được đề xuất hoặc diễn đạt rõ phần bạn muốn hỏi lại."
                    )
                    duplicate_state = {
                        **state,
                        "messages": [
                            *state.get("messages", []),
                            {"role": "user", "content": canonical_message},
                            {"role": "assistant", "content": answer},
                        ][-12:],
                        "last_user_message_normalized": normalized_message,
                    }
                    await app.state.store.save(current_session_id, duplicate_state)
                    for word in answer.split(" "):
                        yield sse("message.delta", {"text": f"{word} "})
                    yield sse("agent.stopped", {"reason": "duplicate_user_message"})
                    yield sse("message.complete", {
                        "intent": "general", "quick_replies": [], "citations": [], "answer_strategy": "high",
                        "confidence_score": 1, "confidence_band": "high", "confidence_reasons": ["Duplicate-turn guard"],
                        "external_search_used": False, "external_search_consent_required": False,
                        "form_code": None, "translation_used": needs_translation,
                    })
                    return

                selected_mode = None
                if workflow.get("status") in {"awaiting_mode", "collecting", "ready_for_review"}:
                    if "điền từng bước" in normalized_message or "cùng agent" in normalized_message:
                        selected_mode = "agent_chat"
                    elif "mở biểu mẫu" in normalized_message or "điền trên biểu mẫu" in normalized_message:
                        selected_mode = "review_form"
                turn_state = state
                if selected_mode:
                    workflow = {**workflow, "status": "collecting", "mode": selected_mode}
                    turn_state = {**state, "agent_workflow": workflow}
                messages = [*turn_state.get("messages", []), {"role": "user", "content": canonical_message}]
                if selected_mode == "review_form":
                    form_code = workflow.get("form_code")
                    answer = "Đã mở biểu mẫu ngay trong khung chat. Bạn có thể điền trực tiếp, chạy Agent kiểm tra, xác nhận dữ liệu, xem PDF và xác nhận lần cuối trước khi gửi mô phỏng."
                    new_state = {
                        **turn_state,
                        "messages": [*messages, {"role": "assistant", "content": answer}][-12:],
                        "last_user_message_normalized": normalized_message,
                    }
                    await app.state.store.save(current_session_id, new_state)
                    for word in answer.split(" "):
                        yield sse("message.delta", {"text": f"{word} "})
                    yield sse("message.complete", {
                        "intent": "form_guidance", "quick_replies": [], "citations": [], "answer_strategy": "high",
                        "confidence_score": 1, "confidence_band": "high", "confidence_reasons": ["User selected review_form mode"],
                        "external_search_used": False, "external_search_consent_required": False,
                        "form_code": form_code, "open_review": False, "translation_used": needs_translation,
                    })
                    return
                if is_submission_simulation_request(canonical_message):
                    form_code = turn_state.get("active_scenario_code")
                    if not form_code:
                        answer = "Bạn chưa có biểu mẫu đang làm. Hãy chọn thủ tục và điền biểu mẫu trước khi nộp mô phỏng."
                        for word in answer.split(" "):
                            yield sse("message.delta", {"text": f"{word} "})
                        yield sse("message.complete", {
                            "intent": "form_guidance", "quick_replies": ["Chọn biểu mẫu"], "citations": [],
                            "answer_strategy": "high", "confidence_score": 1, "confidence_band": "high",
                            "confidence_reasons": ["Không có biểu mẫu active trong phiên"], "external_search_used": False,
                            "external_search_consent_required": False, "form_code": None, "translation_used": needs_translation,
                        })
                        return
                    # Chat text is never sufficient authority to execute a write.
                    # Submission must pass validation, scoped approval, rendered-PDF
                    # review, and a second explicit confirmation in the form UI.
                    answer = (
                        "Tôi đã hiển thị biểu mẫu trong khung chat. Để gửi mô phỏng, bạn cần thẩm định hồ sơ, "
                        "xác nhận dữ liệu sẽ sử dụng, kiểm tra bản PDF và xác nhận lần cuối."
                    )
                    for word in answer.split(" "):
                        yield sse("message.delta", {"text": f"{word} "})
                    yield sse("message.complete", {
                        "intent": "form_guidance", "quick_replies": [], "citations": [],
                        "answer_strategy": "high", "confidence_score": 1, "confidence_band": "high",
                        "confidence_reasons": ["Bắt buộc xác nhận hai bước trên giao diện"], "external_search_used": False,
                        "external_search_consent_required": False, "form_code": form_code,
                        "open_review": False, "translation_used": needs_translation,
                    })
                    return
                result = await app.state.procedure_pipeline.ainvoke({
                    "messages": messages,
                    "request_id": request_id,
                    "language_code": chat_request.language_code,
                    "active_procedure_code": turn_state.get("active_procedure_code"),
                    "administrative_area_code": turn_state.get("administrative_area_code"),
                    "candidate_codes": turn_state.get("candidate_codes", []),
                    "selection_filters": turn_state.get("selection_filters", {}),
                    "pending_filter": turn_state.get("pending_filter"),
                    "locality_required": turn_state.get("locality_required", False),
                    "original_query": turn_state.get("original_query"),
                })
                reply, form_patch = await maybe_fill_form(
                    {**turn_state, "language_code": VIETNAMESE}, result, settings, app.state.procedure_pipeline.procedure_settings, messages,
                )
                form_code = form_patch["form_code"] if form_patch else None
                workflow = turn_state.get("agent_workflow") or {}
                is_new_workflow = bool(form_code and workflow.get("form_code") != form_code)
                validation_rejected = bool(form_patch and form_patch.get("rejected_issues"))
                if is_new_workflow:
                    form_candidate = app.state.procedure_pipeline.procedure_settings.form_candidates[form_code]
                    required_data = [
                        field.field_code
                        for field in form_candidate.fields
                        if field.required
                    ]
                    plan = await build_agent_plan(settings, canonical_message, form_code, required_data)
                    tool_history = record_tool_result([], "lookup_procedure", {"form_code": form_code})
                    tool_history = record_tool_result(tool_history, plan.selected_registration_tool, {"form_code": form_code})
                    workflow = {
                        **plan.model_dump(), "status": "awaiting_mode", "mode": None,
                        "tool_history": tool_history,
                    }
                    reply.answer = (
                        "Tôi đã xác định được mẫu hồ sơ phù hợp. Bạn muốn tự điền biểu mẫu trong khung chat "
                        "hay để tôi hỏi lần lượt từng thông tin cần thiết?"
                    )
                    reply.quick_replies = ["Điền trên biểu mẫu", "Điền từng bước cùng Agent"]
                elif form_patch and workflow.get("mode") == "agent_chat":
                    try:
                        accepted_field_codes = form_patch.get("accepted_field_codes", [])
                        if validation_rejected:
                            yield sse("tool.result", {
                                "name": "validate_form",
                                "ok": False,
                                "issues": [
                                    {"issue_code": issue["issue_code"], "field_code": issue.get("field_code")}
                                    for issue in form_patch["rejected_issues"]
                                ],
                            })
                        elif accepted_field_codes:
                            workflow = {
                                **workflow,
                                "tool_history": record_tool_result(
                                    workflow.get("tool_history", []), "collect_form_data", {"fields": form_patch["fields"]},
                                ),
                            }
                        form_candidate = app.state.procedure_pipeline.procedure_settings.form_candidates[form_code]
                        missing_required = [
                            field.field_code for field in form_candidate.fields
                            if field.required and not form_patch["fields"].get(field.field_code)
                        ]
                        if not missing_required and not validation_rejected:
                            workflow = {**workflow, "status": "ready_for_review"}
                            reply.answer = (
                                "Tôi đã thu thập đủ thông tin bắt buộc. Hãy mở biểu mẫu để kiểm tra toàn bộ dữ liệu, "
                                "thẩm định và xác nhận trước khi tạo PDF."
                            )
                            reply.quick_replies = ["Mở biểu mẫu để kiểm tra"]
                        if accepted_field_codes:
                            yield sse("tool.result", {"name": "collect_form_data", "ok": True, "field_count": len(form_patch["fields"])})
                    except AgentLoopStopped:
                        reply.answer = "Agent đã dừng vì tool thu thập dữ liệu trả cùng một kết quả hai lần liên tiếp. Hãy cung cấp thông tin mới hoặc chuyển sang biểu mẫu."
                        reply.quick_replies = ["Mở biểu mẫu và rà soát"]
                        workflow = {**workflow, "status": "loop_stopped"}
                        yield sse("agent.stopped", {"reason": "repeated_identical_tool_result"})
                canonical_answer = redact_known_secrets(reply.answer)
                normalized_answer = normalize_untrusted_text(canonical_answer).casefold()
                if normalized_answer and normalized_answer == turn_state.get("last_assistant_answer_normalized") and not validation_rejected:
                    canonical_answer = (
                        "Câu trả lời dự kiến trùng hoàn toàn với lượt trước nên Agent đã dừng để tránh lặp. "
                        "Bạn hãy bổ sung dữ liệu mới hoặc chọn một thao tác khác."
                    )
                    reply.answer = canonical_answer
                    reply.quick_replies = ["Điền trên biểu mẫu"] if form_code else []
                    workflow = {**workflow, "status": "loop_stopped", "stop_reason": "duplicate_assistant_answer"}
                    yield sse("agent.stopped", {"reason": "duplicate_assistant_answer"})
                reply.answer = canonical_answer
                if needs_translation:
                    reply.answer = await app.state.translation_service.from_vietnamese(reply.answer, chat_request.language_code)
                    reply.quick_replies = [
                        await app.state.translation_service.from_vietnamese(value, chat_request.language_code)
                        for value in reply.quick_replies
                    ]
                for word in reply.answer.split(" "):
                    yield sse("message.delta", {"text": f"{word} "})
                    await asyncio.sleep(0)
                new_state = {
                    **turn_state,
                    "messages": [*messages, {"role": "assistant", "content": canonical_answer}][-12:],
                    "language_code": chat_request.language_code,
                    "translation_consent": bool(translation_consent),
                    "intent": reply.intent,
                    "active_procedure_code": result.get("active_procedure_code"),
                    "active_scenario_code": form_code if form_code else turn_state.get("active_scenario_code"),
                    "candidate_codes": result.get("candidate_codes", []),
                    "selection_filters": result.get("selection_filters", {}),
                    "pending_filter": result.get("pending_filter"),
                    "locality_required": result.get("locality_required", False),
                    "administrative_area_code": result.get("administrative_area_code"),
                    "original_query": result.get("original_query"),
                    "form_draft": {**turn_state.get("form_draft", {}), form_code: form_patch["fields"]} if form_patch else turn_state.get("form_draft", {}),
                    "last_validation": turn_state.get("last_validation", {}),
                    "agent_workflow": workflow or turn_state.get("agent_workflow"),
                    "last_user_message_normalized": normalized_message,
                    "last_assistant_answer_normalized": normalize_untrusted_text(canonical_answer).casefold(),
                }
                await app.state.store.save(current_session_id, new_state)
                visible_form_code = form_code
                if workflow.get("mode") != "review_form":
                    visible_form_code = None
                yield sse("message.complete", {
                    "intent": reply.intent,
                    "quick_replies": reply.quick_replies,
                    # Citations belong to the deterministic pipeline's own reply; when
                    # maybe_fill_form overrides `reply` (form_guidance), those citations
                    # are stale/unrelated and must not be shown alongside a different answer.
                    "citations": result.get("citations", []) if reply.intent == "procedure_guidance" else [],
                    "answer_strategy": reply.answer_strategy,
                    "confidence_score": reply.confidence_score,
                    "confidence_band": reply.confidence_band,
                    "confidence_reasons": reply.confidence_reasons,
                    "external_search_used": reply.external_search_used,
                    "external_search_consent_required": reply.external_search_consent_required,
                    "form_code": visible_form_code,
                    "translation_used": needs_translation,
                })
            except TranslationError as exc:
                logger.warning("translation_unavailable request_id=%s session=%s reason=%s", request_id, session_hash(current_session_id), str(exc))
                yield sse("error", {"code": "translation_unavailable", "message": "Không thể dịch yêu cầu lúc này."})
                logger.info("chat_complete request_id=%s session=%s latency_ms=%d", request_id, session_hash(current_session_id), (time.perf_counter() - started) * 1000)
            except Exception as exc:  # Keep the SSE connection protocol stable for clients.
                logger.exception("chat_error request_id=%s session=%s error=%s", request_id, session_hash(current_session_id), type(exc).__name__)
                yield sse("error", {"code": "chat_unavailable", "message": "Không thể xử lý yêu cầu lúc này."})

        stream_response = StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
        if is_new:
            set_session_cookie(stream_response, current_session_id)
        return stream_response

    @app.get("/api/v1/sources/{procedure_code}")
    async def source_pdf(procedure_code: str) -> FileResponse:
        """Serve only a published procedure PDF selected by its catalog code."""
        async with app.state.database.connect() as connection:
            pdf_path = await connection.scalar(text("""
                SELECT pc.pdf_path FROM procedure_catalog pc JOIN procedure_snapshot ps ON ps.id = pc.snapshot_id
                WHERE pc.procedure_code = :code AND ps.status = 'published' ORDER BY ps.crawled_at DESC LIMIT 1
            """), {"code": procedure_code})
        if not pdf_path:
            raise HTTPException(status_code=404, detail="Published source not found")
        root = settings.procedure_snapshot_dir.resolve()
        target = (root / pdf_path).resolve()
        if root not in target.parents or not target.is_file():
            raise HTTPException(status_code=404, detail="Source file not found")
        return FileResponse(target, media_type="application/pdf", filename=target.name)

    def _form_candidate_or_404(form_code: str):
        candidate = app.state.procedure_pipeline.procedure_settings.form_candidates.get(form_code)
        if candidate is None:
            raise HTTPException(status_code=404, detail="Unknown form_code")
        return candidate

    @app.get("/api/v1/forms/{form_code}/schema")
    async def form_schema(form_code: str) -> FormSchemaResponse:
        candidate = _form_candidate_or_404(form_code)
        return FormSchemaResponse(
            form_code=candidate.form_code,
            title_vi=candidate.title_vi,
            groups=[
                FormGroupSchema(group_code=group.group_code, label_vi=group.label_vi, display_order=group.display_order)
                for group in candidate.groups
            ],
            fields=[
                FormFieldSchema(
                    field_code=field.field_code,
                    label_vi=field.label_vi,
                    group_code=field.group_code,
                    data_type=field.data_type,
                    required=field.required,
                    enum_values=list(field.validation.enum_values) if field.validation.enum_values else None,
                )
                for field in candidate.fields
            ],
        )

    @app.get("/api/v1/forms/{form_code}/draft")
    async def get_form_draft(
        form_code: str, http_response: Response, session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name),
    ) -> FormDraftResponse:
        _form_candidate_or_404(form_code)
        current_session_id, state, is_new = await ensure_session(session_id)
        if is_new:
            set_session_cookie(http_response, current_session_id)
        return FormDraftResponse(form_code=form_code, fields=state.get("form_draft", {}).get(form_code, {}), updated_at=state.get("updated_at"))

    @app.put("/api/v1/forms/{form_code}/draft")
    async def update_form_draft(
        form_code: str,
        payload: FormDraftUpdateRequest,
        http_response: Response,
        session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name),
    ) -> FormDraftResponse:
        _form_candidate_or_404(form_code)
        current_session_id, state, is_new = await ensure_session(session_id)
        if is_new:
            set_session_cookie(http_response, current_session_id)
        merged = {**state.get("form_draft", {}).get(form_code, {}), **payload.fields}
        workflow = state.get("agent_workflow") or {}
        new_state = {
            **state,
            "form_draft": {**state.get("form_draft", {}), form_code: merged},
            "submission_approvals": {},
            "agent_workflow": {**workflow, "form_code": form_code, "status": "collecting"} if workflow else workflow,
        }
        await app.state.store.save(current_session_id, new_state)
        return FormDraftResponse(form_code=form_code, fields=merged, updated_at=new_state.get("updated_at"))

    @app.post("/api/v1/forms/{form_code}/validate")
    async def validate_form_draft(
        form_code: str, http_response: Response, session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name),
    ) -> ValidationResult:
        candidate = _form_candidate_or_404(form_code)
        current_session_id, state, is_new = await ensure_session(session_id)
        if is_new:
            set_session_cookie(http_response, current_session_id)
        draft = state.get("form_draft", {}).get(form_code, {})
        draft_hash = canonical_input_hash(draft)
        stored_validation = state.get("last_validation", {}).get(form_code)
        # Validation is an idempotent user action. Reuse the trusted result when
        # the exact draft was already validated instead of spending another AI
        # review/tool call or tripping the autonomous-agent loop guard.
        if stored_validation and stored_validation.get("input_hash") == draft_hash:
            return ValidationResult.model_validate(stored_validation)
        base_result = validate_form(candidate, draft)
        ai_issues = await ai_review_form(settings, candidate, draft, base_result.issues)
        result = merge_ai_issues(base_result, ai_issues)
        workflow = state.get("agent_workflow") or {"form_code": form_code, "status": "validating", "tool_history": []}
        result_fingerprint = {
            "form_code": result.form_code,
            "input_hash": result.input_hash,
            "status": result.status,
            "summary": result.summary.model_dump(),
            "issues": [issue.model_dump() for issue in result.issues],
        }
        try:
            tool_history = record_tool_result(workflow.get("tool_history", []), "validate_form", result_fingerprint)
        except AgentLoopStopped as exc:
            stopped_state = {**state, "agent_workflow": {**workflow, "status": "loop_stopped", "stop_reason": str(exc)}}
            await app.state.store.save(current_session_id, stopped_state)
            raise HTTPException(status_code=409, detail=f"agent_loop_stopped:{exc}") from exc
        new_state = {
            **state,
            "last_validation": {**state.get("last_validation", {}), form_code: result.model_dump()},
            "submission_approvals": {},
            "agent_workflow": {**workflow, "status": "review_ready" if result.summary.blocking_error == 0 else "needs_correction", "tool_history": tool_history},
        }
        await app.state.store.save(current_session_id, new_state)
        return result

    @app.post("/api/v1/forms/{form_code}/exports/pdf")
    async def export_form_pdf(
        form_code: str,
        payload: FormExportRequest,
        http_response: Response,
        session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name),
    ) -> Response:
        candidate = _form_candidate_or_404(form_code)
        current_session_id, state, is_new = await ensure_session(session_id)
        if is_new:
            set_session_cookie(http_response, current_session_id)
        stored = state.get("last_validation", {}).get(form_code)
        if not stored or stored.get("validation_id") != payload.validation_id:
            raise HTTPException(status_code=409, detail="Unknown or mismatched validation_id; validate the form again")
        draft = state.get("form_draft", {}).get(form_code, {})
        if canonical_input_hash(draft) != stored.get("input_hash"):
            raise HTTPException(status_code=409, detail="Form data changed since validation; validate again before exporting")
        if stored.get("summary", {}).get("blocking_error", 0) > 0:
            raise HTTPException(status_code=422, detail="Form still has blocking errors; fix them before exporting")
        try:
            pdf_bytes = render_export(candidate, draft)
        except ExportError as exc:
            raise HTTPException(status_code=422, detail=f"export_failed:{exc.reason}:{exc.field_code}") from exc
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{form_code.lower()}.pdf"'},
        )

    @app.post("/api/v1/forms/{form_code}/submissions/approval", response_model=SubmissionApprovalResponse)
    async def preview_submission_approval(
        form_code: str,
        payload: SubmissionApprovalRequest,
        http_response: Response,
        session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name),
    ) -> SubmissionApprovalResponse:
        candidate = _form_candidate_or_404(form_code)
        current_session_id, state, is_new = await ensure_session(session_id)
        if is_new:
            set_session_cookie(http_response, current_session_id)
        validation = state.get("last_validation", {}).get(form_code)
        if not validation or validation.get("validation_id") != payload.validation_id:
            raise HTTPException(status_code=409, detail="validation_required_or_mismatched")
        draft = state.get("form_draft", {}).get(form_code, {})
        disclosed_fields = [field.label_vi for field in candidate.fields if draft.get(field.field_code) not in (None, "", [])]
        try:
            approval = create_submission_approval(
                form_code=form_code, draft=draft, validation=validation, disclosed_fields=disclosed_fields,
            )
        except SubmissionSimulationError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.reason) from exc
        new_state = {
            **state,
            "submission_approvals": {**state.get("submission_approvals", {}), approval["approval_id"]: approval},
        }
        await app.state.store.save(current_session_id, new_state)
        return SubmissionApprovalResponse.model_validate(approval)

    @app.post("/api/v1/forms/{form_code}/submissions/simulate", response_model=SimulatedSubmissionResponse)
    async def simulate_form_submission(
        form_code: str,
        payload: SimulatedSubmissionRequest,
        http_response: Response,
        session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name),
    ) -> SimulatedSubmissionResponse:
        candidate = _form_candidate_or_404(form_code)
        current_session_id, state, is_new = await ensure_session(session_id)
        if is_new:
            set_session_cookie(http_response, current_session_id)
        validation = state.get("last_validation", {}).get(form_code)
        if not validation or validation.get("validation_id") != payload.validation_id:
            raise HTTPException(status_code=409, detail="validation_required_or_mismatched")
        approval = state.get("submission_approvals", {}).get(payload.approval_id or "")
        draft = state.get("form_draft", {}).get(form_code, {})
        existing = next((item for item in reversed(state.get("simulated_submissions", [])) if item.get("validation_id") == payload.validation_id), None)
        if existing:
            return SimulatedSubmissionResponse.model_validate(existing)
        try:
            pdf_bytes = render_export(candidate, draft)
        except ExportError as exc:
            raise HTTPException(status_code=422, detail=f"export_failed:{exc.reason}:{exc.field_code}") from exc
        try:
            receipt = create_simulated_submission(
                form_code=form_code,
                draft=draft,
                validation=validation,
                confirmed=payload.confirmed,
                channel="review_form",
                approval=approval,
                pdf_bytes=pdf_bytes,
            )
        except SubmissionSimulationError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.reason) from exc
        workflow = state.get("agent_workflow") or {"form_code": form_code, "tool_history": []}
        try:
            tool_history = record_tool_result(workflow.get("tool_history", []), "render_pdf", {"pdf_sha256": receipt["pdf_sha256"]})
            tool_history = record_tool_result(tool_history, "submit_simulation", {"receipt_code": receipt["receipt_code"]})
        except AgentLoopStopped as exc:
            raise HTTPException(status_code=409, detail=f"agent_loop_stopped:{exc}") from exc
        consumed_approval = {**approval, "consumed": True}
        new_state = {
            **state,
            "simulated_submissions": [*state.get("simulated_submissions", []), receipt][-10:],
            "simulated_submission_artifacts": {
                **state.get("simulated_submission_artifacts", {}),
                receipt["submission_id"]: base64.b64encode(pdf_bytes).decode("ascii"),
            },
            "submission_approvals": {**state.get("submission_approvals", {}), consumed_approval["approval_id"]: consumed_approval},
            "agent_workflow": {**workflow, "status": "submitted", "tool_history": tool_history},
        }
        await app.state.store.save(current_session_id, new_state)
        logger.info(
            "simulated_submission_complete session=%s form_code=%s receipt_code=%s",
            session_hash(current_session_id), form_code, receipt["receipt_code"],
        )
        return SimulatedSubmissionResponse.model_validate(receipt)

    @app.get("/api/v1/submissions/{submission_id}/artifact.pdf")
    async def download_simulated_submission_artifact(
        submission_id: str,
        session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name),
    ) -> Response:
        if not session_id:
            raise HTTPException(status_code=404, detail="submission_not_found")
        state = await app.state.store.get(session_id)
        encoded = (state or {}).get("simulated_submission_artifacts", {}).get(submission_id)
        if not encoded:
            raise HTTPException(status_code=404, detail="submission_not_found")
        pdf_bytes = base64.b64decode(encoded)
        if not pdf_bytes.startswith(b"%PDF-"):
            raise HTTPException(status_code=500, detail="submission_artifact_corrupt")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{submission_id}.pdf"'},
        )

    return app


app = create_app()
