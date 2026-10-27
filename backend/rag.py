import json
import re

from fastapi import HTTPException
from langchain_community.vectorstores import Chroma
from langchain_anthropic import ChatAnthropic
from langchain_ollama import OllamaLLM
from langchain_openai import ChatOpenAI

from embedding import get_embedding
from paths import CHROMA_ROOT_STR
from services.provider_service import get_provider


def _get_llm(provider: str, model: str, api_key: str | None):
    config = get_provider(provider)
    if config is None:
        raise ValueError(f"Unknown LLM provider: {provider}")

    if config.kind == "ollama":
        return OllamaLLM(model=model)

    if config.needs_api_key and not api_key:
        raise ValueError(f"{config.name} is selected but no API key was provided.")

    if config.kind == "anthropic":
        kwargs: dict = {"model": model, "api_key": api_key}
        if config.base_url:
            kwargs["base_url"] = config.base_url
        return ChatAnthropic(**kwargs)

    # Some OpenAI-compatible local servers (e.g. LM Studio) reject requests
    # without an Authorization header — send a harmless placeholder key.
    openai_kwargs: dict = {
        "model": model,
        "base_url": config.base_url,
        "api_key": api_key or "not-needed",
    }
    # OpenRouter identifies applications via these attribution headers —
    # sending them is required for correct routing on some models and
    # avoids spurious 403s on requests without an identifiable origin.
    if config.base_url and "openrouter.ai" in config.base_url:
        openai_kwargs["default_headers"] = {
            "HTTP-Referer": "https://lumina.app",
            "X-Title": "Lumina",
        }
    return ChatOpenAI(**openai_kwargs)


# Providers format LLM failures as "Error code: 409 - {...}" /
# "status code: 403 - {...}". Extract the HTTP code and, when present,
# the provider's inner human-readable message from the payload.
_PROVIDER_ERROR_CODE = re.compile(
    r"(?:error|status)\s*code[:=]\s*(\d{3})", re.IGNORECASE
)
_INNER_MESSAGE = re.compile(r"['\"]message['\"]\s*:\s*['\"]([^'\"]{0,300})")

_PROVIDER_ERROR_HINTS = {
    401: "Authentication failed — the API key for {name} is invalid or expired. Check it in Settings.",
    403: "The model '{model}' only accepts agentic traffic — it is built for multi-agent interfaces and cannot be used for normal chat. Pick a different model.",
    404: "The model '{model}' is not available (it may have been renamed or discontinued). Pick a different model.",
    409: "The model '{model}' is temporarily overloaded upstream. Try again in a moment or switch to another model.",
    429: "Rate limit reached — free models share capacity. Wait briefly, switch models, or add your own API key for higher limits.",
}


def _provider_display_name(provider: str) -> str:
    config = get_provider(provider)
    return config.name if config is not None else provider


def _friendly_llm_error(e: Exception, provider: str, model: str) -> HTTPException:
    raw = str(e)
    low = raw.lower()

    if "connection refused" in low or "could not connect" in low:
        return HTTPException(
            status_code=503,
            detail=(
                "LLM provider is unreachable — check that Ollama or "
                "LM Studio is running, or verify network access."
            ),
        )

    if "timeout" in low or "timed out" in low:
        return HTTPException(
            status_code=504,
            detail="The model took too long to respond. Try a smaller or faster model.",
        )

    code_match = _PROVIDER_ERROR_CODE.search(raw)
    inner = _INNER_MESSAGE.search(raw)
    inner_text = f" (provider said: {inner.group(1)})" if inner else ""

    if code_match:
        code = int(code_match.group(1))
        hint = _PROVIDER_ERROR_HINTS.get(code)
        if hint is not None:
            return HTTPException(
                status_code=code,
                detail=hint.format(
                    name=_provider_display_name(provider), model=model
                )
                + inner_text,
            )
        if code == 400:
            return HTTPException(
                status_code=400,
                detail="The provider rejected the request" + inner_text,
            )
        return HTTPException(
            status_code=502,
            detail=f"Upstream provider error (HTTP {code})" + inner_text,
        )

    return HTTPException(status_code=500, detail=raw[:300])


def _llm_text(llm, prompt: str, provider: str, model: str) -> str:
    try:
        response = llm.invoke(prompt)
    except Exception as e:
        raise _friendly_llm_error(e, provider, model)
    return response.content if hasattr(response, "content") else str(response)


def _format_memory(memory_entries: list[str] | None) -> str:
    if not memory_entries:
        return "Nothing yet."
    return "\n".join(f"- {entry}" for entry in memory_entries)


def _format_history(conversation_history: list[dict] | None) -> str | None:
    if not conversation_history:
        return None
    lines = []
    for message in conversation_history:
        speaker = "User" if message.get("role") == "user" else "Lumina"
        lines.append(f"{speaker}: {message.get('content', '')}")
    return "\n".join(lines)


def retrieve_with_sources(
    query: str, workspace_id: str, db=None, k: int = 3
) -> tuple[list, list[dict]]:
    """Retrieve the top-k chunks for a workspace and map them to their source
    documents (deduplicated, first/closest chunk wins per file)."""
    store = Chroma(
        collection_name=workspace_id,
        persist_directory=CHROMA_ROOT_STR,
        embedding_function=get_embedding(),
    )
    docs = store.as_retriever(search_kwargs={"k": k}).invoke(query)

    sources: list[dict] = []
    if db is not None:
        from db import crud

        seen_files: set[str] = set()
        for chunk in docs:
            saved = chunk.metadata.get("source_filename")
            if not saved or saved in seen_files:
                continue
            seen_files.add(saved)
            row = crud.get_document_by_saved_filename(db, workspace_id, saved)
            page = chunk.metadata.get("page")
            sources.append(
                {
                    "original_filename": (
                        row.original_filename if row is not None else saved
                    ),
                    "excerpt": chunk.page_content[:150],
                    "page": page + 1 if isinstance(page, int) else None,
                }
            )
    return docs, sources


def build_tutor_prompt(
    query: str,
    context: str,
    memory_entries: list[str] | None,
    conversation_history: list[dict] | None,
) -> str:
    memory_block = _format_memory(memory_entries)
    history_block = _format_history(conversation_history)

    history_section = ""
    if history_block:
        history_section = f"""
Recent conversation:
{history_block}

"""

    return f"""You are Lumina, a personalized AI tutor.

What you know about this user:
{memory_block}

{history_section}Relevant knowledge from uploaded documents:
{context}

User's question:
{query}

Answer:
"""


def ask_lumina(
    query: str,
    workspace_id: str,
    provider: str = "ollama",
    model: str = "qwen3:8b",
    api_key: str | None = None,
    memory_entries: list[str] | None = None,
    conversation_history: list[dict] | None = None,
    db=None,
) -> dict:
    docs, sources = retrieve_with_sources(query, workspace_id, db)
    context = (
        "\n\n".join(doc.page_content for doc in docs)
        if docs
        else "No relevant documents found."
    )
    prompt = build_tutor_prompt(query, context, memory_entries, conversation_history)
    llm = _get_llm(provider, model, api_key)
    return {
        "answer": _llm_text(llm, prompt, provider, model),
        "sources": sources,
    }


def extract_memory(
    question: str,
    answer: str,
    provider: str,
    model: str,
    api_key: str | None,
) -> list[str]:
    prompt = f"""Given this exchange, extract facts worth remembering about the user's learning style,
preferences, knowledge gaps, or study habits. Return a JSON array of short strings.
Return [] if nothing is worth remembering. Return only valid JSON, no other text.

User: {question}
Assistant: {answer}"""

    llm = _get_llm(provider, model, api_key)
    raw = _llm_text(llm, prompt, provider, model).strip()

    # Strip markdown fences if the model wraps the JSON
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[len("json"):].strip()

    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return []

    if not isinstance(parsed, list):
        return []

    return [str(item) for item in parsed if isinstance(item, str)]
