from __future__ import annotations

import time

from ..domain import PromptSuite, SampleResult
from ..providers.base import BaseProvider


def collect_provider_samples(
    provider: BaseProvider,
    prompt_suite: PromptSuite,
    repetitions: int,
    cooldown_ms: int,
) -> list[SampleResult]:
    results: list[SampleResult] = []
    for case in prompt_suite.cases:
        for attempt in range(1, repetitions + 1):
            sample = provider.generate(case.prompt, attempt)
            sample.case_id = case.case_id
            results.append(sample)
            if cooldown_ms > 0:
                time.sleep(cooldown_ms / 1000)
    return results
