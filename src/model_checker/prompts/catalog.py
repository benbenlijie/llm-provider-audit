from __future__ import annotations

from ..domain import PromptSuite


def prompt_case_index(prompt_suite: PromptSuite) -> dict[str, dict[str, str]]:
    return {
        case.case_id: {
            "category": case.category,
            "prompt": case.prompt,
        }
        for case in prompt_suite.cases
    }
