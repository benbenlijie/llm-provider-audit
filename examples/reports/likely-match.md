# Audit Report: example-openai-compatible-likely-match

- Run ID: `example-likely-match-2026-04-19T00-00-00Z`
- Claimed model: `example-frontier-model`
- Reference provider: `reference_official`

## Reference Calibration

- Calibrated cases: `3`
- Uncalibrated cases: `0`
- Baseline `instruction_following` self similarity: `0.910`
- Baseline `reasoning_style` self similarity: `0.880`
- Baseline `structured_output` self similarity: `0.940`

## Targets

## Target: `target_gateway`

- Verdict: `likely_match`
- Requested model: `example-frontier-model`
- Requested model listed in `/v1/models`: `True`
- Provider health OK: `True`
- Weighted relative similarity: `0.973`
- Weighted cross similarity ratio: `0.966`
- Weighted tail probability: `0.721`
- Outlier case count: `0`
- Calibrated cases used: `3`
- Mean failure rate: `0.000`
- Mean JSON pass delta: `0.000`
- Mean expectation pass delta: `0.000`
- Reasons: target similarity is within calibrated reference variance, negative-control margin is positive, fingerprint nearest anchor is the reference provider
- Best negative control: `example_lower_tier_control`
- Relative margin vs best negative: `0.214`
- Fingerprint available: `True`
- Fingerprint label: `reference_like`
- Fingerprint reasons: nearest anchor matches reference
- Fingerprint nearest anchor: `reference_official`
- Fingerprint nearest anchor similarity: `0.961`
- Fingerprint open-set suspicious: `False`
- Fingerprint open-set threshold used: `0.820`
- Fingerprint open-set threshold source: `example-anchor-calibration`
- Fingerprint reference similarity: `0.961`
- Fingerprint best alternative anchor: `example_lower_tier_control`
- Fingerprint best alternative similarity: `0.747`
- Fingerprint reference margin: `0.214`

| Case | Category | Type | Tags | Calibrated | Relative Similarity | Tail Prob. | Cross Similarity | Exact Match | Failure Rate |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `json_contract_001` | `structured_output` | `json_contract` | `format, schema` | `true` | `0.989` | `0.820` | `0.930` | `0.667` | `0.000` |
| `instruction_edge_001` | `instruction_following` | `instruction_constraint` | `constraints` | `true` | `0.978` | `0.680` | `0.890` | `0.333` | `0.000` |
| `style_reasoning_001` | `reasoning_style` | `style_fingerprint` | `style, reasoning` | `true` | `0.955` | `0.630` | `0.840` | `0.000` | `0.000` |

### Sample Excerpts

- Case `style_reasoning_001` (`reasoning_style`), relative similarity `0.955`, tail prob `0.630`, type `style_fingerprint`, tags `style, reasoning`, target expectation pass `1.000`, reference expectation pass `1.000`
  Reference: `Concise analysis with caveats, then a bounded recommendation.`
  Target: `Concise analysis with caveats, then a bounded recommendation.`
- Case `instruction_edge_001` (`instruction_following`), relative similarity `0.978`, tail prob `0.680`, type `instruction_constraint`, tags `constraints`, target expectation pass `1.000`, reference expectation pass `1.000`
  Reference: `The answer uses exactly two bullet points and avoids the forbidden token.`
  Target: `The answer uses exactly two bullet points and avoids the forbidden token.`
- Case `json_contract_001` (`structured_output`), relative similarity `0.989`, tail prob `0.820`, type `json_contract`, tags `format, schema`, target expectation pass `1.000`, reference expectation pass `1.000`
  Reference: `{\"decision\":\"approve\",\"risk\":\"low\",\"reasons\":[\"all required fields present\"]}`
  Target: `{\"decision\":\"approve\",\"risk\":\"low\",\"reasons\":[\"all required fields present\"]}`
