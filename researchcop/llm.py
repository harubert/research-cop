"""Thin wrapper around the Anthropic Messages API: structured JSON output, server tools, pause_turn."""
from __future__ import annotations

import base64
import json
from pathlib import Path

import anthropic

MAX_CONTINUATIONS = 5
_client = None


class ModelError(RuntimeError):
    pass


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        # credentials from the environment (ANTHROPIC_API_KEY or an `ant auth login` profile)
        _client = anthropic.Anthropic(max_retries=4)
    return _client


def pdf_block(pdf_path: Path) -> dict:
    data = base64.standard_b64encode(pdf_path.read_bytes()).decode("ascii")
    return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": data}}


def tools_for(code_execution: bool, web_search: bool) -> list[dict]:
    tools = []
    if code_execution:
        tools.append({"type": "code_execution_20260120", "name": "code_execution"})
    if web_search:
        tools.append({"type": "web_search_20260209", "name": "web_search"})
    return tools


def structured(model: str, system: str, content: list[dict], schema: dict, *, tools=None,
               effort: str = "high", max_tokens: int = 64000) -> tuple[dict, dict]:
    """Run one request and return (parsed JSON, usage/meta). Resumes server-tool pauses."""
    messages = [{"role": "user", "content": content}]
    usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    kwargs = dict(
        model=model,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
    )
    if tools:
        kwargs["tools"] = tools
    response = None
    for _ in range(MAX_CONTINUATIONS + 1):
        with client().messages.stream(messages=messages, **kwargs) as stream:
            response = stream.get_final_message()
        for k in usage:
            usage[k] += getattr(response.usage, k, 0) or 0
        if response.stop_reason != "pause_turn":
            break
        # resume: send the paused assistant turn back unchanged, no extra user message
        messages = messages[:1] + [{"role": "assistant", "content": response.content}]
    if response.stop_reason == "refusal":
        raise ModelError(f"model declined the request ({getattr(response, 'stop_details', None)})")
    if response.stop_reason == "max_tokens":
        raise ModelError("output limit reached before the JSON was complete")
    texts = [b.text for b in response.content if b.type == "text" and b.text.strip()]
    if not texts:
        raise ModelError(f"no JSON in response (stop_reason={response.stop_reason})")
    try:
        data = json.loads(texts[-1])
    except json.JSONDecodeError as e:
        raise ModelError(f"invalid JSON in response: {e}") from e
    meta = {"model": response.model, "request_id": getattr(response, "_request_id", None), "usage": usage}
    return data, meta
