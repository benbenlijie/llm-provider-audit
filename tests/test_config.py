import os
from pathlib import Path
import unittest
from unittest.mock import patch

from model_checker.config import load_audit_config


REPO_ROOT = Path(__file__).resolve().parents[1]


class ConfigTests(unittest.TestCase):
    def test_load_default_config(self) -> None:
        config = load_audit_config(
            REPO_ROOT / "configs/audits/gpt-5.4-router-baseline.yaml"
        )
        self.assertEqual(config.claimed_model, "gpt-5.4")
        self.assertEqual(config.reference_provider, "official")
        self.assertIn("wyzai", config.providers)
        self.assertEqual(config.prompt_suite.name, "default")
        self.assertIn("official_gpt52", config.negative_controls)
        self.assertEqual(config.providers["official_gpt52"].model_override, "gpt-5.2")
        self.assertGreater(config.scoring.min_weighted_tail_probability, 0)
        self.assertTrue(config.fingerprinting.enabled)
        self.assertGreater(config.fingerprinting.open_set_min_anchor_similarity, 0)
        self.assertEqual(config.fingerprinting.reference_margin_scale, 0.2)
        self.assertFalse(config.anchor_calibration.enabled)
        self.assertEqual(config.anchor_calibration.batch_count, 3)
        self.assertEqual(config.router.root, Path("/path/to/codex-router"))
        self.assertEqual(config.router.env_file, Path("/path/to/codex-router/router.env"))
        self.assertEqual(config.router.node_bin, "node")

    def test_load_smoke_wyzai_with_multiple_negative_controls(self) -> None:
        config = load_audit_config(
            REPO_ROOT / "configs/audits/smoke-wyzai.yaml"
        )
        self.assertEqual(config.negative_controls, ["official_gpt54_compact", "official_gpt52"])
        self.assertEqual(config.providers["official_gpt54_compact"].model_override, "gpt-5.4-openai-compact")
        self.assertEqual(config.fingerprinting.min_reference_margin, 0.05)
        self.assertEqual(config.fingerprinting.reference_margin_scale, 0.2)

    def test_load_smoke_askmanyai_uses_public_example_endpoint(self) -> None:
        config = load_audit_config(
            REPO_ROOT / "configs/audits/smoke-askmanyai.yaml"
        )
        self.assertEqual(config.sampling.repetitions, 2)
        self.assertFalse(config.providers["askmanyai"].trust_env)
        self.assertEqual(config.providers["askmanyai"].base_url, "https://your-askmanyai-endpoint.example")

    def test_load_generic_openai_compatible_template(self) -> None:
        config = load_audit_config(
            REPO_ROOT / "configs/audits/openai-compatible-template.yaml"
        )
        self.assertEqual(config.target_providers, ["candidate_provider"])
        self.assertEqual(config.providers["candidate_provider"].api_key_env, "MODEL_CHECKER_TARGET_API_KEY")
        self.assertEqual(config.providers["candidate_provider"].base_url, "https://provider.example/v1")
        self.assertFalse(config.providers["candidate_provider"].trust_env)

    def test_load_deep_askmanyai_uses_differential_prompt_suite(self) -> None:
        config = load_audit_config(
            REPO_ROOT / "configs/audits/deep-askmanyai.yaml"
        )
        self.assertEqual(config.prompt_suite.name, "differential-deep-v1")
        self.assertEqual(config.target_providers, ["askmanyai"])
        self.assertFalse(config.providers["askmanyai"].trust_env)
        self.assertTrue(any(case.discriminator_type for case in config.prompt_suite.cases))
        self.assertTrue(config.anchor_calibration.enabled)
        self.assertEqual(config.anchor_calibration.batch_count, 3)
        self.assertEqual(config.anchor_calibration.batch_repetitions, 2)
        self.assertEqual(config.anchor_calibration.threshold_margin, 0.02)

    def test_load_generic_openai_compatible_deep_template(self) -> None:
        config = load_audit_config(
            REPO_ROOT / "configs/audits/openai-compatible-deep-template.yaml"
        )
        self.assertEqual(config.prompt_suite.name, "differential-deep-v1")
        self.assertTrue(config.anchor_calibration.enabled)
        self.assertEqual(config.target_providers, ["candidate_provider"])
        self.assertEqual(config.providers["candidate_provider"].api_key_env, "MODEL_CHECKER_TARGET_API_KEY")

    def test_load_audit_config_expands_environment_variables(self) -> None:
        with patch.dict(
            os.environ,
            {
                "MODEL_CHECKER_ROUTER_ROOT": "/tmp/router-root",
                "MODEL_CHECKER_ROUTER_ENV_FILE": "/tmp/router-root/router.env",
                "MODEL_CHECKER_NODE_BIN": "/tmp/node",
                "MODEL_CHECKER_ASKMANY_BASE_URL": "http://127.0.0.1:3333",
            },
            clear=False,
        ):
            config = load_audit_config(REPO_ROOT / "configs/audits/deep-askmanyai.yaml")
        self.assertEqual(config.router.root, Path("/tmp/router-root"))
        self.assertEqual(config.router.env_file, Path("/tmp/router-root/router.env"))
        self.assertEqual(config.router.node_bin, "/tmp/node")
        self.assertEqual(config.providers["askmanyai"].base_url, "http://127.0.0.1:3333")


if __name__ == "__main__":
    unittest.main()
