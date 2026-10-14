"""Optional Sentry tracing for the agent. Off unless SENTRY_DSN is set (pip install sentry-sdk).

Spans follow Sentry's AI-agent conventions, so the Sentry "AI Agents" view shows each question
as: invoke_agent (plan) -> execute_tool (credit_limit, forecast, ...) -> chat (Gemma calls),
with latency and token counts. Nothing about customers is attached: only tool names and timings.
"""
from __future__ import annotations

import contextlib
import os

_on = False


def init() -> bool:
    global _on
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return False
    try:
        import sentry_sdk
        sentry_sdk.init(dsn=dsn, traces_sample_rate=1.0, send_default_pii=False,
                        environment="demo" if os.environ.get("UDHAAR_DEMO") == "1" else "shop")
        _on = True
    except Exception as e:  # tracing must never break the counter
        print(f"[udhaar] Sentry off: {e!r}")
    return _on


@contextlib.contextmanager
def span(op: str, name: str, model: str | None = None, tool: str | None = None, **data):
    if not _on:
        yield None
        return
    import sentry_sdk
    with sentry_sdk.start_span(op=op, name=f"{op.split('.')[-1]} {name}") as s:
        s.set_data("gen_ai.system", "ollama" if model else "udhaar")
        if model:
            s.set_data("gen_ai.request.model", model)
        if tool:
            s.set_data("gen_ai.tool.name", tool)
        for k, v in data.items():
            s.set_data(k, v)
        yield s


def usage(s, resp: dict) -> None:
    """Record Ollama's token counts on a span."""
    if s is not None and resp:
        s.set_data("gen_ai.usage.input_tokens", resp.get("prompt_eval_count", 0))
        s.set_data("gen_ai.usage.output_tokens", resp.get("eval_count", 0))
