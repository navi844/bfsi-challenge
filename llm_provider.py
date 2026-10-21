"""OpenAI-only chat wrapper. THIS FILE HAS NO OBSERVABILITY OF ANY KIND -
no spans, and `usage` below is read from the API response and then
immediately discarded. The token counts are right there in `response.usage`
on every single call; nothing converts them into a cost or records them
anywhere. That's Step 5 of the outline: add pricing.py, and both a
lab.cost_usd span attribute AND a proper cost metric - once Step 1 has
given you a tracer and a meter to record them with."""
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI
from pricing import compute_cost_usd
from otel_setup import get_meter
from opentelemetry import trace

ENV_FILE = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_FILE)

DEFAULT_MODEL = "gpt-4o-mini"
_client: Optional[OpenAI] = None

# Metric instrument (created at import time from configured MeterProvider)
_meter = get_meter("bfsi-assistant")
_cost_histogram = None
try:
    _cost_histogram = _meter.create_histogram("lab.cost_usd", description="USD cost per call")
except Exception:
    _cost_histogram = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                f"OPENAI_API_KEY is not set. Check your .env file at: {ENV_FILE}"
            )
        _client = OpenAI(api_key=api_key)
    return _client


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass
class AgentTurn:
    content: Optional[str]
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = ""
    raw: object = None


def chat_raw(messages, tools=None, model: str = DEFAULT_MODEL,
             temperature: Optional[float] = None) -> AgentTurn:
    client = _get_client()

    kwargs = {"model": model, "messages": messages}
    if tools:
        kwargs["tools"] = tools
    if temperature is not None:
        kwargs["temperature"] = temperature

    response = client.chat.completions.create(**kwargs)
    choice = response.choices[0]

    # response.usage.prompt_tokens / completion_tokens exist right here, on
    # every call - and nothing in this file does anything with them. Look
    # for this comment again once you're on Step 5.

    # Compute and record cost (span attribute + histogram metric)
    usage = None
    try:
        usage = getattr(response, "usage", None) or (response.get("usage") if isinstance(response, dict) else None)
    except Exception:
        usage = None

    prompt_tokens = None
    completion_tokens = None
    if usage is not None:
        try:
            prompt_tokens = getattr(usage, "prompt_tokens", None) or (usage.get("prompt_tokens") if isinstance(usage, dict) else None)
            completion_tokens = getattr(usage, "completion_tokens", None) or (usage.get("completion_tokens") if isinstance(usage, dict) else None)
        except Exception:
            prompt_tokens = completion_tokens = None

    cost = compute_cost_usd(prompt_tokens or 0, completion_tokens or 0, model)

    # set span attribute on current span
    try:
        span = trace.get_current_span()
        if span is not None:
            span.set_attribute("lab.cost_usd", float(cost))
    except Exception:
        pass

    # record histogram metric if available
    try:
        if _cost_histogram is not None:
            _cost_histogram.record(float(cost), {"model": model or DEFAULT_MODEL})
    except Exception:
        pass

    tool_calls = []
    for tc in (choice.message.tool_calls or []):
        tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=tc.function.arguments))

    return AgentTurn(
        content=choice.message.content,
        tool_calls=tool_calls,
        finish_reason=choice.finish_reason,
        raw=response,
    )
