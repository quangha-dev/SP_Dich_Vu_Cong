import pytest
from fakeredis.aioredis import FakeRedis

from app.session_store import SessionStore


@pytest.mark.asyncio
async def test_session_is_created_saved_and_deleted() -> None:
    redis = FakeRedis(decode_responses=True)
    store = SessionStore(redis, ttl_seconds=1800)

    session_id = await store.create()
    assert await store.get(session_id) == {
        "messages": [],
        "language_code": "vi",
        "translation_consent": False,
        "intent": "general",
        "active_procedure_code": None,
        "active_scenario_code": None,
        "candidate_codes": [],
        "selection_filters": {},
        "pending_filter": None,
        "locality_required": False,
        "administrative_area_code": None,
        "original_query": None,
        "form_draft": {},
        "last_validation": {},
        "simulated_submissions": [],
        "simulated_submission_artifacts": {},
        "submission_approvals": {},
        "agent_workflow": None,
        "last_user_message_normalized": None,
        "last_assistant_answer_normalized": None,
        "security_event_count": 0,
        "security_events": [],
        "pending_clarification_request": None,
    }

    await store.save(session_id, {"messages": [{"role": "user", "content": "Xin chào"}], "intent": "general"})
    assert (await store.get(session_id))["messages"][0]["role"] == "user"

    await store.delete(session_id)
    assert await store.get(session_id) is None
