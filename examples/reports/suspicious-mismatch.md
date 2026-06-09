# Audit Report: example-openai-compatible-suspicious-mismatch

- Run ID: `example-suspicious-mismatch-2026-04-19T00-00-00Z`
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

- Verdict: `suspicious_mismatch`
- Requested model: `example-frontier-model`
- Requested model listed in `/v1/models`: `True`
- Provider health OK: `True`
- Weighted relative similarity: `0.612`
- Weighted cross similarity ratio: `0.587`
- Weighted tail probability: `0.041`
- Outlier case count: `2`
- Calibrated cases used: `3`
- Mean failure rate: `0.000`
- Mean JSON pass delta: `0.333`
- Mean expectation pass delta: `0.333`
- Reasons: weighted similarity falls outside calibrated reference variance, multiple calibrated cases are low-tail outliers, target is also close to the lower-tier negative control
- Best negative control: `example_lower_tier_control`
- Relative margin vs best negative: `-0.048`
- Fingerprint available: `True`
- Fingerprint label: `ambiguous_or_alternative_like`
- Fingerprint reasons: nearest anchor is not the reference provider, reference margin is below calibrated threshold
- Fingerprint nearest anchor: `example_lower_tier_control`
- Fingerprint nearest anchor similarity: `0.641`
- Fingerprint open-set suspicious: `True`
- Fingerprint open-set threshold used: `0.820`
- Fingerprint open-set threshold source: `example-anchor-calibration`
- Fingerprint reference similarity: `0.593`
- Fingerprint best alternative anchor: `example_lower_tier_control`
- Fingerprint best alternative similarity: `0.641`
- Fingerprint reference margin: `-0.048`

| Case | Category | Type | Tags | Calibrated | Relative Similarity | Tail Prob. | Cross Similarity | Exact Match | Failure Rate |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `json_contract_001` | `structured_output` | `json_contract` | `format, schema` | `true` | `0.511` | `0.020` | `0.480` | `0.000` | `0.000` |
| `instruction_edge_001` | `instruction_following` | `instruction_constraint` | `constraints` | `true` | `0.593` | `0.050` | `0.540` | `0.000` | `0.000` |
| `style_reasoning_001` | `reasoning_style` | `style_fingerprint` | `style, reasoning` | `true` | `0.716` | `0.160` | `0.630` | `0.000` | `0.000` |

### Sample Excerpts

- Case `json_contract_001` (`structured_output`), relative similarity `0.511`, tail prob `0.020`, type `json_contract`, tags `format, schema`, target expectation pass `0.000`, reference expectation pass `1.000`
  Reference: `{\"decision\":\"approve\",\"risk\":\"low\",\"reasons\":[\"all required fields present\"]}`
  Target: `I can help with that. The decision is probably approved because the risk seems low.`
- Case `instruction_edge_001` (`instruction_following`), relative similarity `0.593`, tail prob `0.050`, type `instruction_constraint`, tags `constraints`, target expectation pass `0.000`, reference expectation pass `1.000`
  Reference: `The answer uses exactly two bullet points and avoids the forbidden token.`
  Target: `Here is a longer explanation with three bullets and an extra caveat.`
- Case `style_reasoning_001` (`reasoning_style`), relative similarity `0.716`, tail prob `0.160`, type `style_fingerprint`, tags `style, reasoning`, target expectation pass `1.000`, reference expectation pass `1.000`
  Reference: `Concise analysis with caveats, then a bounded recommendation.`
  Target: `Verbose generic answer with a broad recommendation and fewer caveats.`
