"""Agentic ask endpoint — streams progress events over SSE.

Mirror of routes/chat.py's contract with two additions:
  - progress events are emitted during the run (step / agent / final)
  - the payload may carry an explicit `agent` ("teacher" | "quiz") override;
    omit it to let the router decide.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agents import orchestrator
from db.database import get_db
from db.schemas import ConversationMessageCreate, ConversationRename
from routes.chat import _auto_title, _run_memory_extraction
from services import (
    conversation_service,
    memory_service,
    settings_service,
    workspace_service,
)
from services.provider_service import get_provider

router = APIRouter(tags=["agent"])


class AgentAskRequest(BaseModel):
    question: str
    conversation_id: str
    agent: str | None = None  # "teacher" | "quiz" | None (auto-route)


@router.post("/workspaces/{workspace_id}/agent/ask")
async def agent_ask(
    workspace_id: str,
    request: AgentAskRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    workspace = workspace_service.get_workspace(db, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )

    conversation = conversation_service.get_conversation(
        db, request.conversation_id
    )
    if conversation is None or conversation.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found in this workspace",
        )

    effective_provider, effective_model = settings_service.resolve_llm(
        db,
        conversation.llm_provider,
        conversation.llm_model,
        workspace.llm_provider,
        workspace.llm_model,
    )

    api_key = None
    provider_config = get_provider(effective_provider, db)
    if provider_config is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown LLM provider: {effective_provider}",
        )
    if provider_config.needs_api_key:
        api_key = settings_service.get_api_key(db, effective_provider)
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Provider {provider_config.name} has no API key configured "
                    "in Settings."
                ),
            )

    is_first_message = (
        len(conversation_service.list_messages(db, conversation.id)) == 0
    )
    user_message = conversation_service.append_message(
        db,
        conversation.id,
        ConversationMessageCreate(role="user", content=request.question),
    )

    memory_entries = memory_service.get_prompt_memory(db, workspace.id)
    history = conversation_service.get_recent_history(db, conversation.id, limit=6)

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def emit(event: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, event)

    outcome: dict = {}

    def worker() -> None:
        try:
            result = orchestrator.run(
                request.question,
                workspace.id,
                effective_provider,
                effective_model,
                api_key,
                memory_entries,
                history,
                db,
                emit,
                forced_agent=request.agent,
            )
            outcome["result"] = result
        except HTTPException as e:
            outcome["error"] = (e.status_code, e.detail)
        except Exception as e:  # agent guardrail: never crash the stream
            outcome["error"] = (500, str(e)[:300])

    async def run_worker() -> None:
        try:
            await asyncio.to_thread(worker)
        finally:
            queue.put_nowait({"event": "__done__"})

    async def stream_events():
        runner = asyncio.create_task(run_worker())
        try:
            while True:
                event = await queue.get()
                if event.get("event") == "__done__":
                    break
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            await runner

        if "error" in outcome:
            status_code, detail = outcome["error"]
            yield f"data: {json.dumps({'event': 'error', 'status': status_code, 'detail': detail})}\n\n"
            return

        result = outcome["result"]
        answer = result["answer"]

        assistant_message = conversation_service.append_message(
            db,
            conversation.id,
            ConversationMessageCreate(role="assistant", content=answer),
        )

        conversation_name = None
        if is_first_message:
            renamed = conversation_service.rename_conversation(
                db,
                conversation.id,
                ConversationRename(name=_auto_title(request.question)),
            )
            if renamed is not None:
                conversation_name = renamed.name

        final_payload = {
            "event": "final",
            "response": answer,
            "sources": result["sources"],
            "agent": result["agent"],
            "agent_label": result["agent_label"],
            "user_message_id": user_message.id,
            "assistant_message_id": assistant_message.id,
        }
        if conversation_name:
            final_payload["conversation_name"] = conversation_name

        yield f"data: {json.dumps(final_payload)}\n\n"

        background_tasks.add_task(
            _run_memory_extraction,
            request.question,
            answer,
            workspace.id,
            effective_provider,
            effective_model,
            api_key,
        )

    return StreamingResponse(
        stream_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
