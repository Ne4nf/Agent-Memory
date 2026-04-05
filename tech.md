# Source Package

This package contains the as-built backend for the `logo_generate` workflow.
It is the application layer that sits on top of AI Hub SDK contracts and
coordinates Stage A, Stage B, and Stage C for logo generation.

## Overview

The current runtime flow is stream-first and runs inside a single task execution:

1. `LogoGenerateTask` receives `LogoGenerateInput` through AI Hub SDK.
2. Stage A detects logo intent, extracts fields, analyzes references, and checks the required-field gate.
3. If `brand_name` or `industry` is missing, the flow returns clarification chunks and stops.
4. If the gate passes, Stage B runs web research and guideline inference.
5. Stage C generates logo options and returns the final payload.

The current implementation is fail-closed. It does not fabricate research results,
guidelines, or logo options when provider calls fail.

## Main entrypoints

- `source/tasks/logo_generate.py`
- `source/services/stage_a/handler.py`
- `source/services/stage_a/orchestrator.py`
- `source/services/stage_b/orchestrator.py`
- `source/services/stage_c/orchestrator.py`

## Package structure

- `source/context/` - in-memory session checkpoint store and conflict handling.
- `source/schemas/` - request, response, and stage contract models.
- `source/services/` - orchestration and business services for all stages.
- `source/tasks/` - AI Hub SDK task adapter.
- `source/utils/` - logger and utility helpers.
- `source/config.py` - runtime configuration and environment settings.
- `source/logger.py` - shared logging setup.

## Stage flow

### Stage A - Intake and clarification

Stage A is responsible for:

- intent detection,
- input extraction,
- reference image analysis,
- required-field validation,
- clarification question generation when required fields are missing.

Current behavior worth knowing:

- `InputExtractionTool` and `ReferenceImageAnalyzeTool` run in parallel after intent detection passes.
- The required fields are `brand_name` and `industry`.
- Merge precedence is explicit request fields > extracted fields > previous session context in clarification follow-up mode.

### Stage B - Web research and guideline inference

Stage B enriches the merged context with web research and then builds the design guideline.

Current behavior worth knowing:

- Research runs only after the required-field gate passes.
- Web research keeps fetchable images only.
- Gemini analysis uses backend-fetched image bytes.
- The stage checkpoints the research context and guideline into `SessionContextStore`.

### Stage C - Logo generation

Stage C loads the latest guideline from session state and generates logo options.

Current behavior worth knowing:

- Generation is parallel per option.
- The final output includes `guideline`, `required_field_state`, and `options`.
- If the guideline checkpoint is missing, Stage C fails explicitly with `GUIDELINE_NOT_READY`.

## Key contracts

- Input schema: `LogoGenerateInput`
- Output stream schema: `LogoGenerateTaskOutput`
- Session state: `SessionContextStore`
- Shared status builder: `LifecycleStatusManager`
- Final payload builder: `AsyncPayloadAssembler`
- Design trace projection: `DesignMemoryService`

## Session and memory behavior

The runtime keeps session state in `SessionContextStore` and uses versioned
checkpoints to avoid stale writes.

Important notes:

- Session scope is keyed by `session_id`.
- `context_version` is used for optimistic conflict detection.
- `source/design.md` is a trace/audit projection, not the authoritative runtime store.
- The current `SessionContextStore` is in-memory and does not survive process restarts.

## Lazy exports

`source/services/__init__.py` exposes the main service classes through lazy loading:

- `StreamIntakeHandler`
- `StreamIntakeOrchestrator`
- `StreamGenerationOrchestrator`
- `LogoDesignToolset`
- `WebResearchService`
- `OptionGenerationService`
- `LifecycleStatusManager`
- `AsyncPayloadAssembler`
- `DesignMemoryService`

## Practical notes

- This package is optimized for a single `logo_generate` task type.
- The flow is designed for deterministic clarification and contract-safe output.
- Provider errors should be handled as explicit failures, not hidden behind fallback content.
- If you add a new stage or provider, keep the schema contracts stable and update the stage README sections above.

## Related files

- [technical-design.md](../technical-design.md)
- [source-code-review.md](../source-code-review.md)
# Source Package

This package contains the as-built backend for the `logo_generate` workflow.
It is the application layer that sits on top of AI Hub SDK contracts and
coordinates Stage A, Stage B, and Stage C for logo generation.

## Overview

The current runtime flow is stream-first and runs inside a single task execution:

1. `LogoGenerateTask` receives `LogoGenerateInput` through AI Hub SDK.
2. Stage A detects logo intent, extracts fields, analyzes references, and checks the required-field gate.
3. If `brand_name` or `industry` is missing, the flow returns clarification chunks and stops.
4. If the gate passes, Stage B runs web research and guideline inference.
5. Stage C generates logo options and returns the final payload.

The current implementation is fail-closed. It does not fabricate research results,
guidelines, or logo options when provider calls fail.

## Main entrypoints

- `source/tasks/logo_generate.py`
- `source/services/stage_a/handler.py`
- `source/services/stage_a/orchestrator.py`
- `source/services/stage_b/orchestrator.py`
- `source/services/stage_c/orchestrator.py`

## Package structure

- `source/context/` - in-memory session checkpoint store and conflict handling.
- `source/schemas/` - request, response, and stage contract models.
- `source/services/` - orchestration and business services for all stages.
- `source/tasks/` - AI Hub SDK task adapter.
- `source/utils/` - logger and utility helpers.
- `source/config.py` - runtime configuration and environment settings.
- `source/logger.py` - shared logging setup.

## Stage flow

### Stage A - Intake and clarification

Stage A is responsible for:

- intent detection,
- input extraction,
- reference image analysis,
- required-field validation,
- clarification question generation when required fields are missing.

Current behavior worth knowing:

- `InputExtractionTool` and `ReferenceImageAnalyzeTool` run in parallel after intent detection passes.
- The required fields are `brand_name` and `industry`.
- Merge precedence is explicit request fields > extracted fields > previous session context in clarification follow-up mode.

### Stage B - Web research and guideline inference

Stage B enriches the merged context with web research and then builds the design guideline.

Current behavior worth knowing:

- Research runs only after the required-field gate passes.
- Web research keeps fetchable images only.
- Gemini analysis uses backend-fetched image bytes.
- The stage checkpoints the research context and guideline into `SessionContextStore`.

### Stage C - Logo generation

Stage C loads the latest guideline from session state and generates logo options.

Current behavior worth knowing:

- Generation is parallel per option.
- The final output includes `guideline`, `required_field_state`, and `options`.
- If the guideline checkpoint is missing, Stage C fails explicitly with `GUIDELINE_NOT_READY`.

## Key contracts

- Input schema: `LogoGenerateInput`
- Output stream schema: `LogoGenerateTaskOutput`
- Session state: `SessionContextStore`
- Shared status builder: `LifecycleStatusManager`
- Final payload builder: `AsyncPayloadAssembler`
- Design trace projection: `DesignMemoryService`

## Session and memory behavior

The runtime keeps session state in `SessionContextStore` and uses versioned
checkpoints to avoid stale writes.

Important notes:

- Session scope is keyed by `session_id`.
- `context_version` is used for optimistic conflict detection.
- `source/design.md` is a trace/audit projection, not the authoritative runtime store.
- The current `SessionContextStore` is in-memory and does not survive process restarts.

## Lazy exports

`source/services/__init__.py` exposes the main service classes through lazy loading:

- `StreamIntakeHandler`
- `StreamIntakeOrchestrator`
- `StreamGenerationOrchestrator`
- `LogoDesignToolset`
- `WebResearchService`
- `OptionGenerationService`
- `LifecycleStatusManager`
- `AsyncPayloadAssembler`
- `DesignMemoryService`

## Practical notes

- This package is optimized for a single `logo_generate` task type.
- The flow is designed for deterministic clarification and contract-safe output.
- Provider errors should be handled as explicit failures, not hidden behind fallback content.
- If you add a new stage or provider, keep the schema contracts stable and update the stage README sections above.

## Related files

- [technical-design.md](../technical-design.md)
- [source-code-review.md](../source-code-review.md)
