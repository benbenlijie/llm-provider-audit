from __future__ import annotations

from abc import ABC, abstractmethod

from ..domain import ProviderSnapshot, SampleResult


class BaseProvider(ABC):
    def __init__(self, provider_name: str, claimed_model: str) -> None:
        self.provider_name = provider_name
        self.claimed_model = claimed_model

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def __enter__(self) -> "BaseProvider":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    @abstractmethod
    def snapshot(self) -> ProviderSnapshot:
        raise NotImplementedError

    @abstractmethod
    def generate(self, prompt: str, attempt: int) -> SampleResult:
        raise NotImplementedError
