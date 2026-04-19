from __future__ import annotations

from typing import Any

from ..domain import ProviderSnapshot


def compare_metadata(reference: ProviderSnapshot, target: ProviderSnapshot, requested_model: str) -> dict[str, Any]:
    reference_models = reference.models.get("data", []) if isinstance(reference.models, dict) else []
    target_models = target.models.get("data", []) if isinstance(target.models, dict) else []
    reference_model_ids = {item.get("id") for item in reference_models if isinstance(item, dict)}
    target_model_ids = {item.get("id") for item in target_models if isinstance(item, dict)}
    return {
        "reference_requested_model": reference.requested_model,
        "target_requested_model": requested_model,
        "reference_requested_model_listed": reference.requested_model in reference_model_ids,
        "target_requested_model_listed": requested_model in target_model_ids,
        "target_health_ok": bool(target.health.get("ok", True)) if isinstance(target.health, dict) else False,
        "target_base_url": target.base_url,
    }
