"""Orchestrator: route a user message to a specialist agent, emit progress."""

from __future__ import annotations

from typing import Callable

from agents.library import AGENTS, AgentContext
from agents import router


def run(
    question: str,
    workspace_id: str,
    provider: str,
    model: str,
    api_key: str | None,
    memory_entries: list[str],
    conversation_history: list[dict],
    db,
    emit: Callable[[dict], None],
    forced_agent: str | None = None,
) -> dict:
    """Runs sync (call via asyncio.to_thread). Returns
    {"answer", "sources", "agent", "agent_label"}."""

    agent_id = forced_agent
    if agent_id is None:
        mention = router.force_agent(question)
        if mention is None:
            emit({"event": "step", "label": "Figuring out what you need…"})
            agent_id = router.classify(question, provider, model, api_key)
        else:
            agent_id = mention
    if agent_id not in AGENTS:
        agent_id = "teacher"

    agent = AGENTS[agent_id]
    emit({"event": "agent", "agent": agent.id, "agent_label": agent.label})

    ctx = AgentContext(
        question=router.strip_mention(question),
        workspace_id=workspace_id,
        provider=provider,
        model=model,
        api_key=api_key,
        memory_entries=memory_entries,
        conversation_history=conversation_history,
        db=db,
        emit=emit,
    )
    result = agent.handle(ctx)
    return {
        "answer": result["answer"],
        "sources": result.get("sources", []),
        "agent": agent.id,
        "agent_label": agent.label,
        "quiz": result.get("quiz"),
    }
