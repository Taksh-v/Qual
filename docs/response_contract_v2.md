# Response Contract v2

This document defines the normalized writing and response format contract introduced in the renovation.

## Goals
- Keep current API response shapes backward compatible.
- Add a normalized contract metadata block for consistency checks.
- Centralize schema, prompt format, validation, and normalization logic.

## Backward compatibility
- Existing keys such as `question`, `answer`, and `sources` are preserved.
- New contract metadata is appended under `_response_contract`.
- Optional advanced blocks may also appear at top-level without affecting legacy parsing.
- No endpoint path or request body changes are required.

## Contract metadata
Every normalized payload can include:

```json
{
	"_response_contract": {
		"schema_version": "v2",
		"mode": "brief",
		"validation_ok": true,
		"validation_warnings": [],
		"evidence_integrity": null,
		"regime_warning": null,
		"decision_stub": null,
		"counterfactual_result": null,
		"personalization": null
	}
}
```

These five blocks are optional and are only populated when enabled by feature flags or
explicitly provided by the caller. When present, they are mirrored in `_response_contract`
for a stable inspection path. Legacy clients can safely ignore them.

## Canonical response sections
The writing contract targets these sections:
- `Direct answer`
- `Data snapshot`
- `Causal chain`
- `What is happening`
- `Market impact`
- `Predicted events`
- `Scenarios`
- `What to watch`
- `Confidence`

Detailed mode additionally supports:
- `Executive summary`
- `Key risks`
- `Time horizons`

Optional advanced contract blocks (Phase 1 foundation):
- `evidence_integrity`
- `regime_warning`
- `decision_stub`
- `counterfactual_result`
- `personalization`

## Implementation modules
- `intelligence/response_schema.py`: dataclasses for structured response.
- `intelligence/response_builder.py`: mode-specific builders.
- `intelligence/prompt_templates.py`: centralized format instructions.
- `intelligence/response_normalizer.py`: text-to-schema parser.
- `intelligence/response_validator.py`: structural quality checks.
- `intelligence/response_middleware.py`: non-breaking payload normalization.
- `intelligence/response_contract.py`: facade helpers for integration.

## Validation rules (high level)
- Mandatory core fields: direct answer, data snapshot, market impact.
- Scenario probabilities should sum to approximately 100%.
- Predicted events should include trigger and invalidation.
- Warnings are attached in metadata, without breaking existing payloads.
- Optional advanced blocks are schema-validated only when present.

