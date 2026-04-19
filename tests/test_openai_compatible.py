import unittest
from unittest.mock import patch

import httpx

from model_checker.providers.openai_compatible import (
    OpenAICompatibleProvider,
    extract_text_from_payload,
    parse_sse_events,
)


def build_response(
    status_code: int,
    *,
    json_body: dict | None = None,
    text: str | None = None,
    content_type: str = "application/json",
) -> httpx.Response:
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    if json_body is not None:
        return httpx.Response(
            status_code,
            headers={"content-type": content_type},
            json=json_body,
            request=request,
        )
    return httpx.Response(
        status_code,
        headers={"content-type": content_type},
        text=text or "",
        request=request,
    )


class OpenAICompatibleTests(unittest.TestCase):
    def test_parse_sse_events(self) -> None:
        payload = """
event: response.output_text.delta
data: {"type":"response.output_text.delta","delta":"hel"}

event: response.output_text.delta
data: {"type":"response.output_text.delta","delta":"lo"}

event: response.output_text.done
data: {"type":"response.output_text.done","text":"hello"}
""".strip()
        events = parse_sse_events(payload)
        self.assertEqual(len(events), 3)
        text, raw = extract_text_from_payload(payload, "text/event-stream")
        self.assertEqual(text, "hello")
        self.assertEqual(len(raw["events"]), 3)

    def test_generate_falls_back_to_non_stream_after_400_rejection(self) -> None:
        provider = OpenAICompatibleProvider(
            "proxy",
            "gpt-5.4",
            base_url="https://example.test",
            timeout_sec=5,
            max_output_tokens=128,
            trust_env=False,
        )
        with patch.object(
            provider,
            "_request",
            side_effect=[
                build_response(400, json_body={"error": {"message": "stream is not supported"}}),
                build_response(200, json_body={"choices": [{"message": {"content": "fallback answer"}}]}),
            ],
        ) as request_mock:
            sample = provider.generate("hello", attempt=1)

        self.assertTrue(sample.success)
        self.assertEqual(sample.text, "fallback answer")
        self.assertIsNone(sample.error)
        self.assertEqual(request_mock.call_count, 2)
        self.assertFalse(sample.raw_response["request"]["stream"])
        self.assertEqual(sample.raw_response["transport_fallback"]["trigger"], "stream_request_rejected_400")
        self.assertTrue(sample.raw_response["transport_fallback"]["initial_attempt"]["request"]["stream"])

    def test_generate_falls_back_to_non_stream_after_empty_stream_output(self) -> None:
        provider = OpenAICompatibleProvider(
            "proxy",
            "gpt-5.4",
            base_url="https://example.test",
            timeout_sec=5,
            max_output_tokens=128,
            trust_env=False,
        )
        with patch.object(
            provider,
            "_request",
            side_effect=[
                build_response(
                    200,
                    text='data: {"choices":[{"delta":{}}]}\n\ndata: [DONE]\n',
                    content_type="text/event-stream",
                ),
                build_response(200, json_body={"choices": [{"message": {"content": "json fallback"}}]}),
            ],
        ) as request_mock:
            sample = provider.generate("hello", attempt=1)

        self.assertTrue(sample.success)
        self.assertEqual(sample.text, "json fallback")
        self.assertEqual(request_mock.call_count, 2)
        self.assertEqual(sample.raw_response["transport_fallback"]["trigger"], "empty_stream_output")
        self.assertEqual(sample.raw_response["transport_fallback"]["initial_attempt"]["status_code"], 200)


if __name__ == "__main__":
    unittest.main()
