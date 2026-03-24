# Logo Design AI POC

## 1. Overview

### 1.1 POC objective

This POC builds a backend-driven Logo Design Service using a chat-first workflow:

- Input: user query (text, optional image references).
- Backend flow: analyze request, produce reasoning, produce design guideline, generate 3-4 logo options, apply prompt-based edits.
- Output: image URLs (minimum PNG 1024x1024) and edit summary.

Business validation goals:

- Prove users can complete the full loop: request -> analyze -> guideline -> generate -> select -> edit -> regenerate.
- Prove visible reasoning is understandable and useful.
- Prove editing is usable without region-level editing tools.

### 1.2 Success metrics

- >= 90% of requests return a design guideline before image generation starts.
- >= 90% of requests return 3-4 valid logo options.
- >= 85% of sessions complete end-to-end flow without restart.
- >= 85% of edit requests reflect requested changes while preserving core concept.
- p95 time to first reasoning chunk <= 1.5s.
- p95 time to complete 3-4 logo outputs <= 25s.
- On generation/edit failure, actionable error + retry guidance returned <= 3s.

### 1.3 Technical constraints

- Single image model in POC to reduce integration risk.
- No hardcoded business rule engine; use schema-driven and prompt-driven behavior.
- Out of scope: touch edit, smart mark, region/object-level editing.
- Session scope is single-session only.
- Stream API is primary channel for incremental UX.

---

## 2. POC Scope

### 2.1 Build vs Defer

| Area | Build (POC) | Defer |
| :--- | :--- | :--- |
| Intent + input | Detect logo intent, parse text/references, extract brand context | Multi-domain intent classifier |
| Clarification | Ask clarification when needed, allow skip with explicit assumptions | Adaptive multi-turn clarification policy |
| Reasoning | Stream reasoning blocks (input understanding, style inference, assumptions) | Multi-agent debate and self-critique loops |
| Guideline | Generate structured design guideline before generation | Auto-optimization guideline loop via evaluator |
| Generation | Generate 3-4 PNG options from guideline | Multi-model routing and auto-ranking |
| Editing | Prompt-based edit on selected option + edit summary | Region/object-level editing |
| Follow-up | Return quick follow-up suggestions | Personalized recommendation engine |
| Storage/session | Persist output URLs + metadata per request/session | Project library, version history, long-term memory |

---

## 3. System Architecture

### 3.1 Overview

#### 3.1.1 Why this solution

We chose a **streaming-first, task-based architecture** because:

1. **Early visibility** (UX): Emit reasoning and guideline chunks within 1-2s, so users see progress before image generation begins (slow operation).
2. **Modular reuse**: Each capability (analyze, generate, edit) is a task type that can be called independently or composed.
3. **Provider agility**: Tool abstraction lets us swap image generators (Nano Banana → other) without touching core orchestration logic.
4. **Async-ready**: Stream API can later become async (webhook) if frontend drops long-polling.

#### 3.1.2 System architecture diagram (Layered)

```mermaid
graph TB
    FE["Frontend<br/>(Chat UI)"]
    API["Communication Layer<br/>(Stream API)"]
    TASK["Task Execution Layer<br/>(BaseTask + logo_generate/edit)"]
    ORCH["Orchestrator<br/>(planning + LLM calls)"]
    TOOLS["Tools Layer<br/>(LLM tool, ImageGen tool)"]
    GEMINI["Gemini 2.5-flash<br/>(reasoning + guideline)"]
    NANONA["Nano Banana<br/>(gemini-2.5-flash-image)"]
    STORAGE["Storage/CDN<br/>(image URLs)"]

    FE -->|POST /stream| API
    API -->|dispatch by task_type| TASK
    TASK -->|delegate| ORCH
    ORCH -->|call_tool| TOOLS
    TOOLS -->|text API| GEMINI
    TOOLS -->|HTTP/MCP| NANONA
    TOOLS -->|upload| STORAGE
    STORAGE -->|signed URLs| FE
```

#### 3.1.3 System layers & responsibilities

- **Communication layer** (REST API): Route by `task_type`, validate input schema, stream chunks to client.
- **Task layer** (ai-hub-sdk): Define `logo_generate` and `logo_edit` as tasks with structured input/output; register with `ServingMode.STREAM`.
- **Orchestration layer** (Agent + Orchestrator): Call LLM for reasoning/guideline, coordinate tools, emit stream chunks in order.
- **Tool layer** (Function tools + MCP): Stable abstractions for LLM calls and image generation; support timeout, retry, tool filtering.
- **Integration layer** (external APIs): **Gemini 2.5-flash** for reasoning, **Nano Banana (`gemini-2.5-flash-image`)** for image generation.
- **Storage layer** (object storage + CDN): Persist images, return signed/public URLs with TTL.

---

### 3.2 Architecture principles & decision rationale

#### 3.2.1 Task-first

- Each business capability is an independent task: `logo_analyze`, `logo_generate`, `logo_edit`.
- Routing is based on `task_type`, not endpoint-specific hardcoding.
- **Rationale**: Enables reuse by other features (variation, batch generation, A/B testing) without code duplication; scales to multi-model routing in production.

#### 3.2.2 Schema-first

- All contracts use Pydantic: `LogoGenerateInput`, `DesignGuideline`, `StreamEnvelope`.
- Validation at boundary (communication layer); schema changes don't require flow rewrites.
- **Rationale**: Type safety + backward compatibility; new fields = new template logic, not orchestrator changes.

#### 3.2.3 Stream-first

- `POST /internal/v1/tasks/stream` is default execution path.
- Frontend renders by `chunk_type` from `StreamEnvelope`, respects `sequence` for ordering.
- **Rationale**: Achieves p95 first reasoning chunk ≤ 1.5s by streaming tokens early; frontend controls rendering independently.

#### 3.2.4 Tool abstraction

- Agent calls tools behind stable interface: `LLMTool`, `ImageGenerationTool`, `ImageEditTool`.
- Providers swappable: Gemini → OpenAI GPT, Nano Banana → Imagen 4, without touching orchestrator.
- **Rationale**: POC agility (test different models); production upgrade path (enhance quality) without rearchitecting.

---

### 3.3 Component breakdown & external service decisions

Reference for cost and model comparisons used in this section: `docs/guides/model-benchmark.md`.

| Component | Role | External Service | Decision | Cost/Latency | Rationale |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **LLM Tool** (in Orchestrator) | Intent detection, reasoning generation, guideline synthesis | **Gemini 2.5-flash** (streaming) | Text-only input; stream tokens for reasoning chunks | $0.30/1M input, $2.50/1M output; TTFB ~500ms | Fastest TTFB (<1.5s p95); cost-effective for POC; native streaming for chunk emission |
| **Vision Tool** (Analyze stage, optional) | Extract style/color/iconography from reference images | Gemini 2.5-flash multimodal OR deferred | Deferred in POC | N/A | Scope reduction; text-based analysis covers 80% of use cases; can add later |
| **ImageGen Tool** (Generate stage) | Generate 3-4 PNG logos from prompt + guideline | **Gemini API Image** (`gemini-2.5-flash-image`) | Batch-capable; HTTP/MCP endpoint | ~$0.039/image at 1024x1024; SLA ~8-12s per image | Good speed/cost for iterative logo workflow; strong fit for stream-first UX |
| **ImageEdit Tool** (Edit stage) | Regenerate selected logo with edit prompt | **Gemini API Image** (`gemini-2.5-flash-image`) | Same provider for generation and edit consistency | ~$0.039/image at 1024x1024; SLA ~8-12s | Prompt-based edits avoid pixel-level tooling and preserve workflow consistency |
| **Stream Envelope** | Chunk serialization to frontend | ai-hub-sdk built-in (communication.py) | JSON over SSE | Negligible | Native HTTP streaming; frontend handles reconnect; NDJSON serialization |
| **Storage/CDN** | Persist generated images; return URLs to frontend | GCS, S3, or Cloudinary | TBD post-MVP | Depends on provider | Short-lived signed URLs (2-4 hour TTL) to avoid token refresh; CDN caching for common styles |

### 3.3.1 Tool catalog by spec execution steps

The implementation follows the spec execution logic step-by-step. Each step maps to a dedicated tool so orchestration remains explicit and testable.

| Spec Step | Tool Name | Input | Output | External API / Model | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Step 1 - Detect logo intent | `IntentDetectTool` | user query, attachments metadata | `intent=logo|other`, confidence | Gemini API - `gemini-2.5-flash` | Decides whether to route to logo workflow or generic image flow |
| Step 2 - Extract and analyze inputs | `InputExtractionTool` | query, references | `BrandContext` (brand, industry, style, color, symbol) | Gemini API - `gemini-2.5-flash` | Handles text extraction; image extraction can be enabled later |
| Step 2 (optional image analyzer) | `ReferenceImageAnalysisTool` | image URLs / bytes | style, palette, typography cues, icon cues | Gemini image understanding OR deferred | Optional in POC; activated when references are available |
| Step 3 - Clarify request | `ClarificationTool` | partial context + missing fields | clarification questions or skip decision | Gemini API - `gemini-2.5-flash` | Supports skip mode and explicit assumption generation |
| Step 4 - Request analysis and inference | `DesignInferenceTool` | merged context + assumptions | inferred design attributes + reasoning blocks | Gemini API - `gemini-2.5-flash` | Streams visible reasoning (`reasoning` chunks) |
| Step 5 - Design direction selection (optional) | `DirectionOptionTool` | inferred attributes | 3-4 direction options | Gemini API - `gemini-2.5-flash` | Used when request has multiple valid directions |
| Step 6 - Logo generation | `LogoGenerationTool` | selected direction + guideline + generation params | 3-4 raw images + generation metadata | Gemini API Image (Nano Banana) - `gemini-2.5-flash-image` | Primary POC generator for speed/cost |
| Step 6 - Asset persistence | `AssetStorageTool` | raw image bytes, request/session IDs | signed/public URLs | GCS/S3/Cloudinary | Produces URLs for frontend rendering |
| Step 7 - Prompt-based editing | `LogoEditTool` | selected image + edit prompt + guideline | edited image + edit metadata | Gemini API Image (Nano Banana) - `gemini-2.5-flash-image` | Preserves core concept unless user asks redesign |
| Step 9 - Follow-up suggestions | `SuggestionTool` | generated/edit results + session context | follow-up quick actions | Gemini API - `gemini-2.5-flash` | Suggests next actions: recolor, typography tune, regenerate variants |

### 3.3.2 Tool boundaries and ownership

- **Tools only call external systems**: no product orchestration logic inside tools.
- **Orchestrator owns planning**: picks tool order, retries, fallback path, and stream emission order.
- **Task owns business contract**: schema validation, task-level state, final response status.
- **Reason for this split**: easier testing and provider swap; when changing model/provider, only tool adapter changes.

#### 3.3.3 LLM choice rationale: Gemini 2.5-flash

- **When used**: Intent detection (logo_analyze), guideline synthesis (logo_generate), edit intent parsing (logo_edit).
- **Performance vs alternatives**:
  - Gemini 2.5-flash: TTFB ~500ms-1s, pricing (paid tier) $0.30 / 1M input tokens and $2.50 / 1M output tokens.
  - OpenAI GPT-5.4 mini: pricing $0.75 / 1M input tokens and $4.50 / 1M output tokens.
  - OpenAI GPT-5.4 nano: pricing $0.20 / 1M input tokens and $1.25 / 1M output tokens.
  - **Result**: Gemini meets latency + cost targets.
- **Post-POC upgrade**: If reasoning quality needs improvement, run A/B with OpenAI GPT-5.4 mini via the same tool adapter interface (no schema/flow changes).

#### 3.3.4 Image generation choice: Nano Banana (`gemini-2.5-flash-image`)

- **When used**: Logo generation (logo_generate), edit regeneration (logo_edit).
- **Performance vs alternatives**:
  - Nano Banana (`gemini-2.5-flash-image`): official list price about **$0.039/image at 1024x1024**, optimized for high-volume and low latency.
  - Imagen 4 Fast (`imagen-4.0-fast-generate-001`): **$0.02/image**, lower cost but different quality profile and workflow.
  - Imagen 4 Standard (`imagen-4.0-generate-001`): **$0.04/image**, better quality and stronger text rendering.
  - Imagen 4 Ultra (`imagen-4.0-ultra-generate-001`): **$0.06/image**, highest quality in Imagen family.
  - OpenAI GPT-image-1.5: token-based image pricing (not fixed per-image on pricing page), higher flexibility but harder per-image budgeting.
  - **Result**: choose `gemini-2.5-flash-image` for POC to optimize latency and predictable quality for iterative chat edits.
- **Post-POC upgrade**: If brand text rendering quality is below expectation, switch generation tool to `imagen-4.0-generate-001` (same task contract, tool adapter swap only).

---

### 3.4 End-to-end pipeline: Three stages + SLA targets

#### 3.4.1 Stage A: Analyze + Clarification

| Aspect | Detail |
| :--- | :--- |
| **Input Schema** | `LogoGenerateInput`: query (required), references (optional), session_id, allow_skip_clarification (boolean) |
| **Backend tasks** | 1. Extract intent + brand context from query. 2. Analyze reference images (optional; deferred in POC). 3. Decide if clarification needed. 4. Generate explicit assumptions if user skips clarification. |
| **LLM calls** | Gemini 2.5-flash × 1: stream intent detection + clarification decision (streaming tokens for early reasoning emission) |
| **Image API calls** | None |
| **Output chunks** | `clarification` (if needed), `reasoning` (streaming), `guideline` (structured JSON) |
| **Success criteria** | >= 90% of requests return usable guideline; all reasoning understandable; Stage A latency ≤ 1.5s p95 (TTFB mainly) |
| **SLA** | 0-1.5s from request to first reasoning chunk; 1.5-3s to complete guideline |

Spec mapping note:

- Stage A covers spec Step 1, Step 2, Step 3, Step 4, and optional Step 5.

#### 3.4.2 Stage B: Generate

| Aspect | Detail |
| :--- | :--- |
| **Input Schema** | `DesignGuideline` (from Stage A), variation_count (3-4) |
| **Backend tasks** | 1. Refine prompt template from guideline. 2. Call Nano Banana × 3-4 (parallel if capacity allows). 3. Upload each image to storage. 4. Attach metadata: seed, quality_flags (e.g., "has_text_artifacts"), timing |
| **LLM calls** | None (prompt template pre-defined) |
| **Image API calls** | Nano Banana × 3-4 (parallel; ~8-12s each; expect 10-15s wall-clock time) |
| **Output chunks** | `image_option` (×3-4, each with url), `suggestion` (e.g., "Tap to edit colors"), `done` |
| **Success criteria** | >= 90% of requests return 3-4 valid PNG images; no format/encoding errors; total time ≤ 25s p95 |
| **SLA** | 3-20s from Stage A end to first image_option; 10-25s for all 3-4 images + done |

Spec mapping note:

- Stage B covers spec Step 6.

#### 3.4.3 Stage C: Edit

| Aspect | Detail |
| :--- | :--- |
| **Input Schema** | `LogoEditInput`: selected_option_id, selected_image_url, edit_prompt (required), guideline (from Stage A) |
| **Backend tasks** | 1. Parse edit intent (optional: use LLM to disambiguate if prompt complex). 2. Call Nano Banana (img2img mode on selected image). 3. Upload edited result. 4. Generate edit summary ("Changed colors to blue palette, kept icon unchanged") |
| **LLM calls** | Gemini 2.5-flash × 1 (optional): parse edit intent if ambiguous; edit summary generation |
| **Image API calls** | Nano Banana × 1 (img2img/inpainting; ~8-12s SLA) |
| **Output chunks** | `reasoning` (if LLM called), `edit_result` (new image url + summary), `suggestion`, `done` |
| **Success criteria** | >= 85% of edits preserve core concept while reflecting requested change; edit summary accurate |
| **SLA** | 0-12s total (LLM parse ~1s if needed, image generation ~10s, upload ~1s) |

Spec mapping note:

- Stage C covers spec Step 7 and Step 9.

#### 3.4.4 Full sequence: Generate → Edit (Mermaid sequence diagram)

```mermaid
sequenceDiagram
    actor FE as Frontend
    participant API as Stream API
    participant ORCH as Orchestrator
    participant LLM as Gemini 2.5-flash
    participant IMG as Nano Banana
    participant STO as Storage/CDN

    FE->>API: POST /stream (logo_generate)<br/>query + refs
    Note over API,ORCH: === STAGE A: ANALYZE (target: 0-1.5s to first chunk) ===
    API->>ORCH: validate schema + init session
    ORCH->>LLM: analyze(query, refs, context)
    activate LLM
    LLM-->>ORCH: [stream] reasoning tokens
    ORCH-->>API: chunk(reasoning, seq:1)
    API-->>FE: reasoning displayed
    LLM-->>ORCH: [stream] more reasoning + guideline JSON
    deactivate LLM
    ORCH-->>API: chunk(guideline, seq:2)
    API-->>FE: guideline rendered

    Note over API,ORCH: === STAGE B: GENERATE (target: 10-25s total) ===
    ORCH->>IMG: generate(prompt_1) [parallel]
    ORCH->>IMG: generate(prompt_2) [parallel]
    ORCH->>IMG: generate(prompt_3) [parallel]
    ORCH->>IMG: generate(prompt_4) [parallel]

    par Image 1
        IMG-->>ORCH: image_1_bytes
        ORCH->>STO: upload
        STO-->>ORCH: url_1
        ORCH-->>API: chunk(image_option, id:1, seq:3)
        API-->>FE: display image 1
    and Image 2
        IMG-->>ORCH: image_2_bytes
        ORCH->>STO: upload
        STO-->>ORCH: url_2
        ORCH-->>API: chunk(image_option, id:2, seq:4)
        API-->>FE: display image 2
    and Image 3
        IMG-->>ORCH: image_3_bytes
        ORCH->>STO: upload
        STO-->>ORCH: url_3
        ORCH-->>API: chunk(image_option, id:3, seq:5)
        API-->>FE: display image 3
    and Image 4
        IMG-->>ORCH: image_4_bytes
        ORCH->>STO: upload
        STO-->>ORCH: url_4
        ORCH-->>API: chunk(image_option, id:4, seq:6)
        API-->>FE: display image 4
    end

    ORCH-->>API: chunk(suggestion, seq:7)
    ORCH-->>API: chunk(done, seq:8)
    API-->>FE: done signal

    FE->>API: POST /stream (logo_edit)<br/>selected_option_id + edit_prompt + guideline
    Note over API,ORCH: === STAGE C: EDIT (target: 0-12s) ===
    API->>ORCH: validate LogoEditInput
    ORCH->>LLM: (optional) parse_edit_intent(edit_prompt)
    LLM-->>ORCH: edit intent + summary_plan
    ORCH->>IMG: edit(selected_url, edit_prompt)
    IMG-->>ORCH: edited_image_bytes
    ORCH->>STO: upload
    STO-->>ORCH: edited_url
    ORCH-->>API: chunk(reasoning, seq:1)
    ORCH-->>API: chunk(edit_result, edited_url, seq:2)
    API-->>FE: display edited image
    ORCH-->>API: chunk(done, seq:3)
    API-->>FE: done
```

#### 3.4.5 Error handling (target SLA: 3s)

On error in any stage:

1. **Catch & map** (immediate):
   - Catch exceptions; map to error code: `MODEL_TIMEOUT`, `INVALID_INPUT_SCHEMA`, `PROVIDER_UNAVAILABLE`, `EDIT_INTENT_UNPARSEABLE`, `STORAGE_UPLOAD_FAILED`, `SESSION_EXPIRED`, `RATE_LIMIT_EXCEEDED`.

2. **Emit error chunk** (within 3s):
   ```
   chunk(
       error,
       code: "MODEL_TIMEOUT",
       message: "Image generation took too long. Please try again.",
       retryable: true,
       suggested_action: "Retry with fewer options (3 instead of 4)"
   )
   ```

3. **Fallback strategies**:
   - **Stage A error**: Partial guideline + warning + allow proceed to generation (risky but gives user some output).
   - **Stage B partial failure** (2/4 images generated, 2 timeout): Emit successful images + error for remainder + option to retry.
   - **Stage C error**: Offer immediate retry (edit prompt often OK on second attempt).

---

### 3.5 Extensibility & reusability patterns

#### 3.5.1 Adding new inputs/outputs (within existing tasks)

**Example**: Add `ai_improvement_suggestions` to DesignGuideline.

1. Add field to `DesignGuideline` pydantic model.
2. Update Gemini prompt template to generate field.
3. Update Nano Banana prompt template to respond to suggestions.
4. **No changes needed** to communication layer, streaming protocol, or frontend rendering.

#### 3.5.2 Swapping providers (zero impact to tasks/schemas)

**Example**: Upgrade from Nano Banana to Google Imagen 4.

1. Create new `ImageGenTool_Imagen4` adapter with same input/output interface.
2. Update orchestrator config: `image_gen_tool = ImageGenTool_Imagen4()`.
3. **No changes needed** to schemas, stream format, orchestrator flow, or frontend code.

#### 3.5.3 Adding new task type (reuse existing tools)

**Example**: Add `logo_variation` (regenerate selected logo with subtle differences).

1. Define `LogoVariationInput` schema.
2. Register task type in routing table.
3. Implement orchestration flow: Gemini (guideline refinement) → Nano Banana (generation).
4. **Reuse** existing `ImageGenTool`, `StorageTool`, streaming infrastructure.

#### 3.5.4 Rule placement strategy (no hardcoded business rules)

Business logic lives in **three places only**; never in a separate rules engine:

1. **Pydantic schemas** (constraints): `variation_count: int = Field(ge=3, le=4)`.
2. **Prompt templates** (LLM behavior): "For tech startups, prefer: minimalist, sans-serif, monochrome".
3. **Tool adapters** (integration logic): Quality checks, retry policies, fallback thresholds.

**Why**: Rules in prompts + schema are easier to test, audit, and modify than a dedicated rules DSL. They stay close to data.

### 3.5.5 Session memory strategy

Session memory is required to preserve iterative design behavior from spec (generate -> select -> edit -> regenerate).

| Memory Scope | What is stored | TTL | Why |
| :--- | :--- | :--- | :--- |
| Request memory | normalized inputs, parsed intent, extracted attributes | request lifetime | Debugging and replayability |
| Session memory | selected direction, chosen option ID/URL, latest guideline, edit history, assumptions | session TTL (default 24h; configurable) | Needed for coherent edits and follow-up suggestions |
| Artifact memory | image storage keys, signed URL metadata, quality flags, seed | same as asset policy | Reuse and traceability of generated outputs |

Session memory keys (example):

- `session:{session_id}:guideline`
- `session:{session_id}:selected_option`
- `session:{session_id}:edit_history`
- `session:{session_id}:suggestions_context`

Session behavior:

1. On `logo_generate`: initialize session memory and store generated options.
2. On `logo_edit`: load selected option + guideline from session memory.
3. On follow-up prompt: use previous edits + preserved elements for contextual suggestions.
4. On expiry: return actionable message and ask user to regenerate or restore a previous design.

---

### 3.6 Decision record: Why NOT a rule engine

**Considered**: Dedicated rules engine (e.g., Drools, Simple Rules) for:
- Guideline generation rules: `IF (user_industry == "tech") THEN style = "modern"`.
- Quality gates: `IF (artifact_count > 3) THEN reject_image`.

**Rejected because**:
1. **Testing overhead**: Pydantic + prompt templates are easier to unit-test than rule interpreter.
2. **Latency**: Rule interpreter adds 100-200ms of latency; rules live in prompts (co-located with LLM).
3. **Maintainability**: Rules syntax (e.g., Drools RETE) harder to modify than prompt + schema fields.
4. **Flexibility**: Hardcoded rules can't adapt to edge cases; LLM reasoning is inherently flexible + can explain reasoning.

**Outcome**: All business rules encoded in:
- **Pydantic constraints** (hard guardrails).
- **LLM prompts** (soft heuristics + reasoning).
- **Tool adapters** (quality checks + fallbacks).

---

## 4. Data Schema & API Integration

### 4.1 Pydantic models by stage

```python
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, HttpUrl


class ReferenceImage(BaseModel):
    source_url: Optional[HttpUrl] = None
    storage_key: Optional[str] = None


class BrandContext(BaseModel):
    brand_name: Optional[str] = None
    industry: Optional[str] = None
    style_preference: List[str] = Field(default_factory=list)
    color_preference: List[str] = Field(default_factory=list)
    symbol_preference: List[str] = Field(default_factory=list)


class Assumption(BaseModel):
    key: str
    value: str
    reason: str


class ClarificationQuestion(BaseModel):
    key: str
    question: str
    required: bool = False


class DesignGuideline(BaseModel):
    concept_statement: str
    style_direction: List[str]
    color_palette: List[str]
    typography_direction: List[str]
    icon_direction: List[str]
    constraints: List[str]
    assumptions: List[Assumption] = Field(default_factory=list)


class LogoGenerateInput(BaseModel):
    session_id: str
    query: str
    references: List[ReferenceImage] = Field(default_factory=list)
    allow_skip_clarification: bool = True
    variation_count: int = Field(default=4, ge=3, le=4)
    output_format: Literal["png"] = "png"
    output_size: Literal["1024x1024"] = "1024x1024"


class LogoOption(BaseModel):
    option_id: str
    image_url: HttpUrl
    prompt_used: Optional[str] = None
    seed: Optional[int] = None
    quality_flags: List[str] = Field(default_factory=list)


class LogoGenerateOutput(BaseModel):
    guideline: DesignGuideline
    options: List[LogoOption]


class LogoEditInput(BaseModel):
    session_id: str
    selected_option_id: str
    selected_image_url: HttpUrl
    edit_prompt: str
    guideline: DesignGuideline


class LogoEditOutput(BaseModel):
    updated_image_url: HttpUrl
    edit_summary: str
    preserved_elements: List[str] = Field(default_factory=list)


class StreamEnvelope(BaseModel):
    request_id: str
    session_id: str
    task_type: Literal["logo_analyze", "logo_generate", "logo_edit"]
    status: Literal["processing", "completed", "failed"]
    chunk_type: Literal[
        "reasoning", "clarification", "guideline", "image_option",
        "edit_result", "suggestion", "warning", "error", "done"
    ]
    sequence: int
    payload: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

Validation rules:

- `query` is required and non-empty after trim.
- `variation_count` must be 3 or 4.
- Edit flow requires selected image and edit prompt.
- If clarification is skipped, guideline must include explicit assumptions.

### 4.2 Where external APIs are called

- Gemini text API (`gemini-2.5-flash`):
  - Step 1: intent detection (`IntentDetectTool`)
  - Step 2: input extraction (`InputExtractionTool`)
  - Step 3: clarification and assumptions (`ClarificationTool`)
  - Step 4: design inference and reasoning stream (`DesignInferenceTool`)
  - Step 5 (optional): direction options (`DirectionOptionTool`)
  - Step 9: follow-up suggestions (`SuggestionTool`)
- Gemini image API (`gemini-2.5-flash-image`, Nano Banana):
  - Step 6: generate 3-4 logo options (`LogoGenerationTool`)
  - Step 7: prompt-based logo editing (`LogoEditTool`)
- Optional quality mode (runtime switch):
  - Imagen 4 Standard `imagen-4.0-generate-001` as upgrade path for better text rendering and premium quality.
- Optional reference-image analyzer:
  - Enabled when reference image extraction quality is required (deferred in this POC baseline).

### 4.3 Concrete endpoint I/O

- `POST /internal/v1/tasks/stream` (`task_type=logo_generate`)
  - Input:
    - `query`
    - `session_id`
    - `references` (optional)
    - `variation_count` (optional, 3-4)
  - Output stream:
    - `clarification` (if needed)
    - `reasoning`
    - `guideline`
    - `image_option` x 3-4
    - `suggestion`
    - `done`

- `POST /internal/v1/tasks/stream` (`task_type=logo_edit`)
  - Input:
    - `session_id`
    - `selected_option_id`
    - `selected_image_url`
    - `edit_prompt`
    - `guideline`
  - Output stream:
    - `reasoning`
    - `edit_result`
    - `suggestion`
    - `done`

- Optional async fallback:
  - `POST /internal/v1/tasks/submit`
  - `GET /internal/v1/tasks/{task_id}/status`

### 4.4 Session memory schema

```python
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, HttpUrl


class SelectedOptionMemory(BaseModel):
  option_id: str
  image_url: HttpUrl
  selected_at: str


class EditHistoryItem(BaseModel):
  edit_prompt: str
  updated_image_url: HttpUrl
  preserved_elements: List[str] = Field(default_factory=list)
  created_at: str


class LogoSessionMemory(BaseModel):
  session_id: str
  latest_guideline: Optional[DesignGuideline] = None
  selected_option: Optional[SelectedOptionMemory] = None
  generated_options: List[LogoOption] = Field(default_factory=list)
  edit_history: List[EditHistoryItem] = Field(default_factory=list)
  assumptions: List[Assumption] = Field(default_factory=list)
  metadata: Dict[str, str] = Field(default_factory=dict)
```

Storage recommendation:

- Key pattern: `session:{session_id}`
- Suggested backend: Redis for low-latency read/write in stream workflows.
- Default TTL: 24 hours (configurable by environment).
- On missing/expired session: return `SESSION_EXPIRED` error with guidance to regenerate from current prompt.

---

## 5. Risks & Open Issues

### 5.1 Latency

Risk:

- Generating 3-4 images may exceed p95 target.

Mitigation:

- Emit reasoning early for visible progress.
- Parallel generation when provider supports it.
- Timeout and single retry for transient failures.
- Near-timeout fallback from 4 options to 3.

### 5.2 Generation quality

Risk:

- Outputs may drift from guideline or contain artifacts (noise, broken text, pixelation).

Mitigation:

- Apply `quality_flags` per option.
- Keep guideline-first prompt template consistent.
- Return warning + next edit suggestion when quality is below expectation.

### 5.3 Cost

Risk:

- Cost growth from combined LLM + image generation + iterative edits.

Mitigation:

- Track cost per `request_id` and `session_id`.
- Limit edit attempts in POC defaults.
- Reuse guideline/context inside session to reduce unnecessary calls.

### 5.4 Open technical decisions

- Primary frontend streaming protocol for production: NDJSON or gRPC stream.
- TTL and signed URL policy for image assets.
- Whether deterministic seed is required for edit consistency.
- Quality gate policy: hard fail vs soft warning.
