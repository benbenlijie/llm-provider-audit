from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener, urlopen
from typing import Any

import httpx

from ..domain import ProviderSnapshot, SampleResult
from ..sampling.normalizer import normalize_text
from .base import BaseProvider


@dataclass(slots=True)
class _GenerationAttempt:
    stream: bool
    success: bool
    text: str
    error: str | None
    raw_response: dict[str, Any] = field(default_factory=dict)
    fallback_reason: str | None = None


def parse_sse_events(payload: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    current_event = "message"
    current_data: list[str] = []

    def flush() -> None:
        nonlocal current_event, current_data
        if not current_data:
            current_event = "message"
            return
        data = "\n".join(current_data).strip()
        current_data = []
        if not data or data == "[DONE]":
            current_event = "message"
            return
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            parsed = {"raw": data}
        events.append({"event": current_event, "data": parsed})
        current_event = "message"

    for line in payload.splitlines():
        if not line.strip():
            flush()
            continue
        if line.startswith("event:"):
            current_event = line.split(":", 1)[1].strip()
            continue
        if line.startswith("data:"):
            current_data.append(line.split(":", 1)[1].strip())
    flush()
    return events


def extract_text_from_payload(body_text: str, content_type: str) -> tuple[str, dict[str, Any]]:
    content_type = (content_type or "").lower()
    raw_payload: dict[str, Any] = {}

    if "text/event-stream" in content_type or body_text.lstrip().startswith("event:"):
        events = parse_sse_events(body_text)
        parts: list[str] = []
        for event in events:
            data = event["data"]
            if isinstance(data, dict):
                if data.get("type") == "response.output_text.delta":
                    parts.append(str(data.get("delta", "")))
                elif data.get("type") == "response.output_text.done":
                    parts = [str(data.get("text", ""))]
                elif "choices" in data:
                    delta = data["choices"][0].get("delta", {}).get("content", "")
                    if delta:
                        parts.append(str(delta))
        raw_payload = {"events": events}
        return "".join(parts).strip(), raw_payload

    parsed = json.loads(body_text)
    raw_payload = parsed if isinstance(parsed, dict) else {"payload": parsed}

    if isinstance(parsed, dict) and parsed.get("choices"):
        content = parsed["choices"][0].get("message", {}).get("content", "")
        return str(content).strip(), raw_payload

    if isinstance(parsed, dict) and parsed.get("output"):
        parts = []
        for item in parsed["output"]:
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    parts.append(str(content.get("text", "")))
        return "".join(parts).strip(), raw_payload

    return "", raw_payload


def parse_body_payload(body_text: str, content_type: str) -> dict[str, Any]:
    content_type = (content_type or "").lower()
    if not body_text.strip():
        return {}

    if "text/event-stream" in content_type or body_text.lstrip().startswith("event:"):
        return {"events": parse_sse_events(body_text)}

    try:
        parsed = json.loads(body_text)
    except json.JSONDecodeError:
        return {"raw_text": body_text}

    if isinstance(parsed, dict):
        return parsed
    return {"payload": parsed}


def extract_error_message(body_text: str, content_type: str) -> str:
    payload = parse_body_payload(body_text, content_type)
    error = payload.get("error")
    if isinstance(error, dict):
        for key in ("message", "detail", "type", "code"):
            value = error.get(key)
            if value:
                return str(value)
    if isinstance(error, str) and error:
        return error
    for key in ("message", "detail", "error_message"):
        value = payload.get(key)
        if value:
            return str(value)
    if "raw_text" in payload and payload["raw_text"]:
        return str(payload["raw_text"]).strip()
    if payload:
        return json.dumps(payload, ensure_ascii=True)
    return ""


class OpenAICompatibleProvider(BaseProvider):
    def __init__(
        self,
        provider_name: str,
        claimed_model: str,
        *,
        base_url: str,
        timeout_sec: int,
        max_output_tokens: int,
        trust_env: bool = True,
        api_key_env: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(provider_name, claimed_model)
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec
        self.max_output_tokens = max_output_tokens
        self.trust_env = trust_env
        self.api_key_env = api_key_env
        self.extra_headers = headers or {}

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "content-type": "application/json",
            "accept-encoding": "identity",
            **self.extra_headers,
        }
        if self.api_key_env:
            api_key = os.environ.get(self.api_key_env)
            if api_key:
                headers["authorization"] = f"Bearer {api_key}"
        return headers

    def _request(self, method: str, path: str, *, json_body: dict[str, Any] | None = None) -> httpx.Response:
        with httpx.Client(timeout=self.timeout_sec, follow_redirects=True, trust_env=self.trust_env) as client:
            return client.request(
                method,
                f"{self.base_url}{path}",
                headers=self._build_headers(),
                json=json_body,
            )

    def _request_raw_json(self, path: str) -> dict[str, Any]:
        request = Request(
            f"{self.base_url}{path}",
            method="GET",
            headers=self._build_headers(),
        )
        try:
            opener = build_opener(ProxyHandler({})) if not self.trust_env else None
            open_fn = opener.open if opener is not None else urlopen
            with open_fn(request, timeout=self.timeout_sec) as response:
                payload = response.read()
        except URLError as error:
            raise RuntimeError(str(error)) from error

        try:
            return json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError as error:
            raise RuntimeError(f"invalid JSON payload from {path}: {error}") from error

    def _build_generation_body(self, prompt: str, *, stream: bool) -> dict[str, Any]:
        return {
            "model": self.claimed_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.max_output_tokens,
            "stream": stream,
        }

    def _build_attempt_raw_response(
        self,
        *,
        stream: bool,
        response: httpx.Response | None,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        raw_response: dict[str, Any] = {
            "request": {
                "path": "/v1/chat/completions",
                "model": self.claimed_model,
                "stream": stream,
            },
            "body": body,
        }
        if response is not None:
            raw_response["status_code"] = response.status_code
            raw_response["headers"] = dict(response.headers)
        return raw_response

    def _should_fallback_without_stream(
        self,
        *,
        response: httpx.Response | None,
        body_text: str,
        content_type: str,
        text: str,
        error_message: str | None,
    ) -> str | None:
        if text:
            return None

        if response is not None and not response.is_error:
            return "empty_stream_output"

        if response is None:
            return None

        status_code = response.status_code
        if status_code in {400, 422}:
            return f"stream_request_rejected_{status_code}"

        detail = f"{error_message or ''}\n{body_text}".lower()
        if "stream" in detail and any(
            token in detail for token in ("unsupported", "not support", "not supported", "invalid", "sse", "event-stream")
        ):
            return "stream_transport_unsupported"

        if "text/event-stream" in (content_type or "").lower() and not text:
            return "unparseable_stream_payload"

        return None

    def _execute_generation_attempt(self, prompt: str, *, stream: bool) -> _GenerationAttempt:
        response: httpx.Response | None = None
        body_text = ""
        try:
            response = self._request(
                "POST",
                "/v1/chat/completions",
                json_body=self._build_generation_body(prompt, stream=stream),
            )
            body_text = response.text
            response.raise_for_status()
            text, raw_payload = extract_text_from_payload(body_text, response.headers.get("content-type", ""))
            raw_response = self._build_attempt_raw_response(
                stream=stream,
                response=response,
                body=raw_payload,
            )
            fallback_reason = self._should_fallback_without_stream(
                response=response,
                body_text=body_text,
                content_type=response.headers.get("content-type", ""),
                text=text,
                error_message=None if text else "empty_output",
            )
            return _GenerationAttempt(
                stream=stream,
                success=bool(text),
                text=text,
                error=None if text else "empty_output",
                raw_response=raw_response,
                fallback_reason=fallback_reason,
            )
        except Exception as error:
            if isinstance(error, httpx.HTTPStatusError):
                response = error.response
                body_text = response.text
            content_type = response.headers.get("content-type", "") if response is not None else ""
            parsed_body = parse_body_payload(body_text, content_type)
            parsed_error_message = extract_error_message(body_text, content_type)
            error_message = parsed_error_message or str(error)
            raw_response = self._build_attempt_raw_response(
                stream=stream,
                response=response,
                body=parsed_body,
            )
            fallback_reason = self._should_fallback_without_stream(
                response=response,
                body_text=body_text,
                content_type=content_type,
                text="",
                error_message=error_message,
            )
            return _GenerationAttempt(
                stream=stream,
                success=False,
                text="",
                error=error_message,
                raw_response=raw_response,
                fallback_reason=fallback_reason,
            )

    def _merge_fallback_raw_response(
        self,
        initial_attempt: _GenerationAttempt,
        fallback_attempt: _GenerationAttempt,
    ) -> dict[str, Any]:
        raw_response = dict(fallback_attempt.raw_response)
        raw_response["transport_fallback"] = {
            "applied": True,
            "from_stream": initial_attempt.stream,
            "trigger": initial_attempt.fallback_reason,
            "initial_attempt": initial_attempt.raw_response,
        }
        return raw_response

    def snapshot(self) -> ProviderSnapshot:
        health: dict[str, Any]
        models: dict[str, Any]
        try:
            response = self._request("GET", "/health/providers")
            health = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        except Exception as error:
            health = {"ok": False, "error": str(error)}

        try:
            response = self._request("GET", "/v1/models")
            models = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        except Exception as error:
            try:
                models = self._request_raw_json("/v1/models")
            except Exception as fallback_error:
                models = {"ok": False, "error": str(error), "fallback_error": str(fallback_error)}

        return ProviderSnapshot(
            provider=self.provider_name,
            kind="openai_compatible",
            requested_model=self.claimed_model,
            base_url=self.base_url,
            health=health,
            models=models,
        )

    def generate(self, prompt: str, attempt: int) -> SampleResult:
        started = time.perf_counter()
        initial_attempt = self._execute_generation_attempt(prompt, stream=True)
        final_attempt = initial_attempt
        raw_response = initial_attempt.raw_response

        if initial_attempt.fallback_reason:
            fallback_attempt = self._execute_generation_attempt(prompt, stream=False)
            final_attempt = fallback_attempt
            raw_response = self._merge_fallback_raw_response(initial_attempt, fallback_attempt)
            if not fallback_attempt.success:
                raw_response["transport_fallback"]["fallback_attempt"] = fallback_attempt.raw_response

        latency_ms = (time.perf_counter() - started) * 1000
        error = final_attempt.error
        if initial_attempt.fallback_reason and not final_attempt.success:
            error = f"stream_attempt_failed: {initial_attempt.error}; non_stream_attempt_failed: {final_attempt.error}"

        return SampleResult(
            provider=self.provider_name,
            case_id="",
            attempt=attempt,
            success=final_attempt.success,
            text=final_attempt.text,
            normalized_text=normalize_text(final_attempt.text),
            latency_ms=latency_ms,
            error=error,
            raw_response=raw_response,
        )


def similarity_ratio(left: str, right: str) -> float:
    return SequenceMatcher(a=left, b=right).ratio()
