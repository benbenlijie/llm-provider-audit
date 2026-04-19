from __future__ import annotations

import os
import socket
import subprocess
import time

import httpx

from ..domain import ProviderConfig, ProviderSnapshot, RouterConfig
from .openai_compatible import OpenAICompatibleProvider


def _find_free_port(base_port: int) -> int:
    for port in range(base_port, base_port + 200):
        with socket.socket() as handle:
            try:
                handle.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    with socket.socket() as handle:
        handle.bind(("127.0.0.1", 0))
        return int(handle.getsockname()[1])


class RouterInstanceProvider(OpenAICompatibleProvider):
    def __init__(
        self,
        provider_config: ProviderConfig,
        claimed_model: str,
        router_config: RouterConfig,
        timeout_sec: int,
        max_output_tokens: int,
    ) -> None:
        self.provider_config = provider_config
        self.router_config = router_config
        self.port = _find_free_port(router_config.base_port)
        self.process: subprocess.Popen[str] | None = None
        super().__init__(
            provider_name=provider_config.name,
            claimed_model=claimed_model,
            base_url=f"http://127.0.0.1:{self.port}",
            timeout_sec=timeout_sec,
            max_output_tokens=max_output_tokens,
            trust_env=False,
        )

    def _build_env(self) -> dict[str, str]:
        group = self.provider_config.router_group
        env = os.environ.copy()
        env["CODEX_ROUTER_ENV_FILE"] = str(self.router_config.env_file)
        env["HOST"] = "127.0.0.1"
        env["PORT"] = str(self.port)
        env["ROUTER_CIRCUIT_BREAKER_ENABLED"] = "0"
        env["ROUTER_DEBUG_PAYLOADS"] = "0"
        env["ROUTER_PROVIDER_ORDER"] = group or "official"
        env["ROUTER_ENABLE_WYZAI"] = "1" if group == "wyzai" else "0"
        env["ROUTER_ENABLE_OFFICIAL"] = "1" if group == "official" else "0"
        env["ROUTER_ENABLE_FALLBACK"] = "1" if group == "fallback" else "0"
        if self.provider_config.fallback_provider_chain:
            env["FALLBACK_PROVIDER_CHAIN"] = ",".join(self.provider_config.fallback_provider_chain)
        return env

    def start(self) -> None:
        command = [self.router_config.node_bin or "node", "router.mjs"]
        self.process = subprocess.Popen(
            command,
            cwd=self.router_config.root,
            env=self._build_env(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        deadline = time.time() + self.router_config.startup_timeout_sec
        last_error = "router_not_ready"
        while time.time() < deadline:
            try:
                with httpx.Client(timeout=2.0, trust_env=False) as client:
                    response = client.get(f"{self.base_url}/health")
                    if response.status_code == 200:
                        return
            except Exception as error:
                last_error = str(error)
            time.sleep(0.25)
        self.stop()
        raise RuntimeError(f"Failed to start router for {self.provider_name}: {last_error}")

    def stop(self) -> None:
        if not self.process:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.process = None

    def snapshot(self) -> ProviderSnapshot:
        snapshot = super().snapshot()
        snapshot.kind = "router_instance"
        return snapshot
