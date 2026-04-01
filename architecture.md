# Logo Design AI - Complete Architecture & Flow Documentation

**Last Updated:** 2026-04-01  
**Status:** Production  
**Scope:** Full backend flow (Stage A, B, C)

---

## Table of Contents

1. [Quick Overview](#quick-overview)
2. [Code Organization Analysis](#code-organization-analysis)
3. [Progress Mapping](#progress-mapping)
4. [Service Layer Breakdown](#service-layer-breakdown)
5. [Full End-to-End Flow](#full-end-to-end-flow)
6. [Data Flow & Context Management](#data-flow--context-management)
7. [Code Quality & Recommendations](#code-quality--recommendations)
8. [Service File Usage Matrix](#service-file-usage-matrix)

---

## Quick Overview

```
Request → Stream API → Stage A (Intake) → Stage B (Guideline) → 
          ↓
       SessionContext + Merge → Required Field Gate →
          ↓
       Web Research (if needed) → Guideline Inference →
          ↓
    Handoff to Stage C (Async) → Image Generation → Store URLs
```

**Entry Point:** `source/tasks/logo_generate.py` (LogoGenerateTask)  
**Main Orchestrator:** `source/services/stream_intake_handler.py` (StreamIntakeHandler)  
**Session Memory:** `source/context/session_store.py` (SessionContextStore)

---

## Code Organization Analysis

### Directory Structure

```
source/
├── tasks/
│   └── logo_generate.py          # BaseTask implementation (SDK entry)
│
├── services/                      # 12 service files
│   ├── stream_intake_handler.py   # ⭐ CORE: Stage A/B orchestrator
│   ├── llm_logo_tools.py          # ⭐ CORE: LLM tool calls (extraction, inference)
│   ├── option_generation_service.py # ⭐ CORE: Stage C image generation
│   ├── context_merge_service.py   # ⭐ CORE: 3-tier merge (explicit > extracted > session)
│   ├── required_field_gate.py     # ⭐ CORE: brand_name + industry validation
│   ├── guideline_inference_service.py # ⭐ CORE: Default guideline rules per industry
│   ├── web_research_service.py    # ⭐ CORE: Industry context research
│   ├── design_memory_service.py   # ⭐ CORE: Markdown audit trail logging
│   ├── lifecycle_status_manager.py # ⭐ CORE: State machine + progress mapping
│   ├── async_payload_assembler.py # HELPER: Response object builder
│   ├── provider_routing_policy.py # ❓ UNUSED: Imported but never called
│   └── __init__.py                # Service exports
│
├── context/
│   ├── session_store.py           # SessionContextStore (in-memory + CAS)
│   └── __init__.py
│
├── schemas/
│   └── models.py                  # All Pydantic models
│
├── config.py                      # Configuration & env vars
├── logger.py                      # Logging setup
└── __init__.py
```

### Assessment: Code Organization ✅

**Status: GOOD with minor issues**

**Strengths:**
- ✅ Clear separation of concerns (intake, merge, gate, research, guideline, generation)
- ✅ Single Responsibility Principle (each service does one thing)
- ✅ Dependency injection pattern (services passed to StreamIntakeHandler)
- ✅ All core services are actually used
- ✅ No duplicate logic detected (no TODO/FIXME/deprecated markers)
- ✅ Natural flow follows business stages (A → B → C)

**Issues Found:**
- ⚠️ `provider_routing_policy.py` is **imported but never used** (dead code)
- ⚠️ `AsyncPayloadAssembler` is simple but could be inlined as utility function
- ⚠️ Service stateless design is good BUT async_payload_assembler should be static

---

## Progress Mapping

### What is `progress=5`?

**Answer: It doesn't exist in the code.**

Instead, progress is **status-based** using the `StatusEnum`:

```python
# source/services/lifecycle_status_manager.py (lines 17-21)

_DEFAULT_PROGRESS: dict[StatusEnum, int] = {
    StatusEnum.pending: 0,           # Not started
    StatusEnum.processing: 50,       # Mid-execution (Stage A/B in progress)
    StatusEnum.completed: 100,       # Done
    StatusEnum.failed: 100,          # Failed (stop at 100)
}
```

### Progress Resolution Logic

```python
def resolve_progress(self, status: StatusEnum, explicit_progress: int | None = None) -> int:
    # If explicit progress provided (e.g., "Stage: 75%"), use it (clamped 0-100)
    if explicit_progress is not None:
        return max(0, min(100, explicit_progress))
    
    # Otherwise use default mapping from status
    return _DEFAULT_PROGRESS[status]
```

### Actual Runtime Progress (from DYM log)

```
Status     Progress  Stage             Duration
───────────────────────────────────────────────────
pending    0%        Request received  0s
processing 50%       Stage A (intake)  2-5s
processing 50%       Stage B (infer)   40-47s  ← longest
processing 50%       Stage C (gen)     3-8s
completed  100%      All done          50-55s total
```

**Key Point:** Progress jumps 0 → 50 → 100 (no intermediate values). To show granular progress during each stage, services would need to emit explicit progress values OR use alternative mechanisms (e.g., status chunks with progress metadata).

---

## Service Layer Breakdown

### 🔴 Core Services (9 files - Actually Used)

#### 1. **StreamIntakeHandler** (`stream_intake_handler.py`)

**Purpose:** Orchestrate Stage A + Stage B stream flow with clarification loop

**Responsibility:**
- Load session context from store OR start new session
- Call LLM to extract brand_name, industry from query
- Merge extracted with session by precedence rule
- Check required fields (brand_name + industry)
- If missing → emit clarification chunk with suggested questions
- If complete → run web research + guideline inference
- Persist checkpoint to session store (with optimistic locking)
- Log to design.md audit trail

**Key Methods:**
- `stream()`: Main generator yielding response chunks
- `_should_use_session_context()`: 5-condition gate for session reuse
- `_persist_with_cas()`: Optimistic locking write to session store
- `_extract_industry_from_text()`: Fallback industry detection

**Used In:** Logo generate task Stream mode

**Code Quality:** ✅ Good (clear decoupling of concerns)

---

#### 2. **LogoDesignToolset** (`llm_logo_tools.py`)

**Purpose:** All LLM tool invocations via LiteLLM/Google GenAI

**Responsibility:**
- Detect logo intent from query
- Extract brand_name, industry, style, color from query + references
- Analyze reference images for style patterns
- Detect topic swap (user changed industry/brand)
- Generate clarification questions
- Infer design guideline from context
- Support both LiteLLM and Google GenAI fallback

**Key Methods:**
- `detect_intent()` → IntentDecision
- `extract_inputs()` → ExtractionDecision (brand, industry, styles, colors)
- `detect_topic_swap()` → TopicSwapDecision
- `analyze_reference_images()` → StylePatterns
- `suggest_clarifications()` → SuggestedQuestion[]
- `infer_guideline()` → DesignGuideline

**Dependencies:** LiteLLM (primary), Google GenAI (fallback)

**Code Quality:** ✅ Good (comprehensive tool coverage)

**Note:** Largest service file (~500 lines) - consider future refactoring if more tools added

---

#### 3. **ContextMergeService** (`context_merge_service.py`)

**Purpose:** Implement 3-tier precedence merge for BrandContext fields

**Precedence:** explicit (request) > extracted (query) > session (stored)

**What It Merges:**
```python
- brand_name: str | None
- industry: str | None
- style_preference: List[str]
- color_preference: List[str]
- symbol_preference: List[str]
```

**Example:**
```
Input (explicit):    brand_name="Nova"
Extracted (query):   industry="fintech"
Session (stored):    style_preference=["modern"]

Result: brand_name="Nova" (explicit wins)
        industry="fintech" (extracted wins)
        style_preference=["modern"] (session)
```

**Key Methods:**
- `_pick_mandatory()`: First non-empty value in (explicit, extracted, session)
- `_pick_preference_list()`: Merge lists preserving order
- `merge_brand_context()`: Merge one BrandContext field
- `merge_from_input()`: Build explicit from LogoGenerateInput, merge all layers

**Used In:** StreamIntakeHandler (line 410)

**Code Quality:** ✅ Excellent (clear semantics, well-tested)

---

#### 4. **RequiredFieldGateService** (`required_field_gate.py`)

**Purpose:** Validate brand_name + industry are present

**Logic:**
```python
required_keys = ["brand_name", "industry"]

def evaluate(context: BrandContext) -> RequiredFieldGateResult:
    missing = [k for k in required_keys if not context[k]]
    return RequiredFieldGateResult(
        passed=(len(missing) == 0),
        missing_keys=missing
    )
```

**Used In:** StreamIntakeHandler (line 233) before generating guideline

**Code Quality:** ✅ Simple and correct

---

#### 5. **GuidelineInferenceService** (`guideline_inference_service.py`)

**Purpose:** Generate design guideline per industry (lookup-based + LLM fallback)

**Default Rules by Industry:**
```python
if industry == "fintech":
    style=["dynamic", "bold", "geometric"]
    colors=["navy", "cyan", "white"]
    typography=["sans-serif technical"]
    icons=["circuit patterns", "upward arrows"]

elif industry == "sportswear":
    style=["bold sans-serif", "compact athletic"]
    colors=["black", "bold neons"]
    ...
```

**Fallback:** If industry not recognized, call LLM to generate guideline

**Key Methods:**
- `infer()`: Main entry point
- `_default_*()`: Industry-specific lookup rules
- `_concept_variants()`: Generate concept statements

**Used In:** StreamIntakeHandler (line 357)

**Code Quality:** ✅ Good (deterministic defaults + LLM fallback)

---

#### 6. **OptionGenerationService** (`option_generation_service.py`)

**Purpose:** Generate 3-4 logo images in parallel via Google Gemini

**Flow:**
```python
def generate(guideline, task_id, variation_count=4):
    # ThreadPoolExecutor with max_workers=N
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        for i in range(variation_count):
            future = executor.submit(
                _generate_single_option,
                guideline,
                concept_idx=i
            )
            futures.append(future)
    
    # Collect results (waits for all to complete)
    return [f.result() for f in futures]
```

**Per-Image Flow:**
1. Build Gemini prompt from guideline
2. Call Gemini Vision API → get PNG bytes
3. Persist to storage → get image_url
4. Return LogoOption(id, url, metadata)

**Concurrency:** ThreadPoolExecutor (non-async, blocking return)

**Used In:** logo_generate.py Stage C (async/polling pattern)

**Code Quality:** ✅ Good (thread-safe, proper error handling)

---

#### 7. **WebResearchService** (`web_research_service.py`)

**Purpose:** Search web for industry context (design trends, references)

**Flow:**
1. Check if research needed: `should_prioritize_research(query)`
2. Build search queries from brand context (e.g., "fintech logo design")
3. Call SerpAPI for web results + images
4. Analyze text snippets + images with Gemini
5. Return ResearchContext (takeaways + images)

**Key Methods:**
- `should_prioritize_research()`: Heuristic to skip if clear intent
- `_build_queries()`: Generate search terms
- `_search_serpapi()`: Web search
- `_analyze_with_gemini()`: Extract design patterns
- `_build_takeaways()`: Synthesize insights
- `run()`: Main orchestrator

**Used In:** StreamIntakeHandler (line 340) if gate not passed initially

**Code Quality:** ✅ Good (proper error handling, fallbacks)

---

#### 8. **DesignMemoryService** (`design_memory_service.py`)

**Purpose:** Append-only markdown log for audit trail

**Format (design.md):**
```markdown
## Technology
- v1 | ts=2026-03-31T08:53:48Z | session=s1 | ctx_v=1 | brand=DYM | industry=tech | style=[...] | colors=[...] | symbols=[...] | note=initial | concept=A distinctive...
- v2 | ts=... | ... | concept=More refined...
```

**Key Methods:**
- `persist()`: Append versioned record
- `_next_topic_version()`: Auto-increment version
- `_ensure_document()`: Create design.md if missing
- `_format_list()`: Truncate long lists for readability

**Used In:**
- StreamIntakeHandler (line 510) on clarification
- StreamIntakeHandler (line 626) on guideline complete

**Code Quality:** ✅ Good (write-only, no parsing complications)

**Note:** design.md is never READ back into runtime (audit trail only)

---

#### 9. **LifecycleStatusManager** (`lifecycle_status_manager.py`)

**Purpose:** Manage state transitions + progress mapping

**State Machine:**
```
pending  → processing
            ↓
         completed OR failed
            ↓
         (failed can retry)
```

**Key Methods:**
- `can_transition()`: Check if transition allowed
- `transition()`: Perform transition
- `resolve_progress()`: Map status to progress % (or use explicit)
- `build_status_response()`: Create JobStatusResponse

**Used In:** logo_generate.py status polling

**Code Quality:** ✅ Excellent (deterministic, well-documented)

---

### 🟡 Helper Services (2 files)

#### 10. **AsyncPayloadAssembler** (`async_payload_assembler.py`)

**Purpose:** Build response payloads for completed/failed jobs

**Issue:** Very simple (just object creation) - could be inlined as utility function

```python
class AsyncPayloadAssembler:
    def build_completed(task_id, result, metadata=None):
        return JobStatusResponse(
            task_id=task_id,
            status="completed",
            result=result,
            metadata=metadata
        )
```

**Recommendation:** ⚠️ Consider inlining or using Pydantic factory methods

---

### 🔴 Dead Code (1 file)

#### 11. **ProviderRoutingPolicy** (`provider_routing_policy.py`)

**Status:** ❌ **IMPORTED BUT NEVER USED**

**Evidence:**
```python
# Imported in logo_generate.py (line 28)
from source.services import ProviderRoutingPolicy

# Created in logo_generate.py (line 121)
routing_policy=ProviderRoutingPolicy()

# BUT: Never passed to StreamIntakeHandler
# AND: StreamIntakeHandler doesn't accept it
# AND: Never called anywhere
```

**Purpose (if activated):** Provide provider chains for fallback logic

**Recommendation:** ❌ **REMOVE** or implement if planning multi-provider fallback

---

## Full End-to-End Flow

### Request Entry Point

```python
# source/tasks/logo_generate.py
class LogoGenerateTask(BaseTask):
    def stream(self, input: LogoGenerateInput):
        # Initialize services
        session_store = SessionContextStore()
        merge_service = ContextMergeService()
        gate_service = RequiredFieldGateService()
        lifecycle_manager = LifecycleStatusManager()
        toolset = LogoDesignToolset(...)
        web_research = WebResearchService()
        design_memory = DesignMemoryService()
        
        # Delegate to orchestrator
        handler = StreamIntakeHandler(
            session_store=session_store,
            merge_service=merge_service,
            gate_service=gate_service,
            lifecycle_manager=lifecycle_manager,
            toolset=toolset,
            web_research_service=web_research,
            design_memory_service=design_memory
        )
        
        # Yield stream chunks
        yield from handler.stream(input)
```

### Stage A: Intake & Clarification (Lines 150-370 in stream_intake_handler.py)

```
Input: LogoGenerateInput
{
  session_id: "sess-123",
  query: "Design a logo for my tech startup called DYM",
  brand_name: null,
  industry: null,
  use_session_context: true
}

Step 1: Load Session (line 277)
┌─────────────────────────────────
│ store.get(session_id) 
│ → Found: SessionContextState with brand_name="DYM" from previous session
└─────────────────────────────────

Step 2: Extract from New Query (line 281)
┌─────────────────────────────────
│ toolset.extract_inputs(query)
│ → ExtractionDecision {
│     brand_name: "DYM",
│     industry: "technology",
│     style: ["modern"],
│     ...
│   }
└─────────────────────────────────

Step 3: Check Session Context Reuse (line 283)
┌─────────────────────────────────
│ _should_use_session_context(
│   use_flag=true,
│   previous=stored_context,
│   extracted=new_extraction,
│   query=query
│ )
│ 
│ Decision Logic (5 conditions):
│ ✓ flag enabled
│ ✓ history exists
│ ✓ not topic-swapped (tech → tech)
│ ✓ continuation_marker found OR same-topic fallback
│ ✓ not generic query
│ 
│ → Decision: REUSE session context
└─────────────────────────────────

Step 4: Merge by Precedence (line 410)
┌─────────────────────────────────
│ merge_service.merge_from_input(
│   explicit=BrandContext(brand_name="DYM"),
│   extracted=BrandContext(industry="tech"),
│   session=stored_context
│ )
│ 
│ Precedence: explicit > extracted > session
│ Result: BrandContext {
│   brand_name: "DYM",      ← explicit
│   industry: "technology",  ← extracted
│   style: ["modern"],       ← session
│   ...
│ }
└─────────────────────────────────

Step 5: Check Required Fields (line 233)
┌─────────────────────────────────
│ gate_service.evaluate(merged_context)
│ 
│ Required = ["brand_name", "industry"]
│ 
│ ✓ brand_name: "DYM" ✓
│ ✓ industry: "technology" ✓
│ 
│ → Gate PASSED
└─────────────────────────────────

Step 6: Persist Checkpoint (line 426)
┌─────────────────────────────────
│ _persist_with_cas(
│   session_id="sess-123",
│   latest_context=merged_context,
│   expected_version=previous_version+1
│ )
│ 
│ CAS Semantics (optimistic locking):
│ IF store.context_version == expected_version:
│   store[session_id].context_version += 1
│   store[session_id].latest_context = merged_context
│ ELSE:
│   RAISE ContextVersionConflictError
│       (concurrent write detected, retry merge)
└─────────────────────────────────

Step 7: Decide on Web Research (line 340)
┌─────────────────────────────────
│ web_research.should_prioritize_research(query)
│ 
│ Heuristic: If query is vague or industry is specialized
│            "design a logo" (generic) → skip
│            "design a fintech logo" (clear) → skip
│            "design a Web3 DeFi logo" (specialist) → research
│ 
│ → Decision: Skip (query is clear enough)
└─────────────────────────────────

Step 8: Emit Intake Chunk (line 470)
┌─────────────────────────────────
│ Yield chunk {
│   "status": "processing",
│   "progress_percent": 50,
│   "stage": "intake_started",
│   "extracted": {...},
│   "merged": {...}
│ }
└─────────────────────────────────
```

### Stage B: Guideline Inference (Lines 355-395 in stream_intake_handler.py)

```
Input: merged BrandContext { brand_name, industry, style, colors }

Step 1: Infer Guideline (line 357)
┌─────────────────────────────────
│ guideline_service.infer(merged_context)
│ 
│ Industry-specific lookup:
│ if industry == "technology":
│   style = ["dynamic", "geometric", "modern"]
│   colors = ["navy", "cyan", "electric blue"]
│   typography = ["sans-serif", "futuristic"]
│   icons = ["circuit patterns", "nodes", "connections"]
│   concept_variants = [
│     "Connected intelligence",
│     "Digital ecosystem",
│     "Geometric future"
│   ]
│ 
│ Return: DesignGuideline {
│   concept_statement: "Connected digital intelligence...",
│   style_direction: ["dynamic", "geometric"],
│   color_palette: ["navy", "cyan"],
│   ...
│ }
└─────────────────────────────────

Step 2: Persist Guideline Checkpoint (line 426)
┌─────────────────────────────────
│ _persist_with_cas(
│   latest_guideline=guideline,
│   expected_version=ctx_v+1
│ )
└─────────────────────────────────

Step 3: Log to design.md (line 626)
┌─────────────────────────────────
│ design_memory.persist(
│   topic="technology",
│   context=merged_context,
│   guideline=guideline,
│   note="guideline_completed"
│ )
│ 
│ Appends to design.md:
│ - v11 | ts=2026-03-31T10:32:21Z | session=sess-123 | ... | concept=Connected...
└─────────────────────────────────

Step 4: Emit Guideline Chunk (line 640)
┌─────────────────────────────────
│ Yield chunk {
│   "status": "processing",
│   "progress_percent": 50,
│   "stage": "guideline_completed",
│   "guideline": {...},
│   "next_action": "submit_async_generation_task"
│ }
└─────────────────────────────────
```

### Handoff to Stage C: Async Image Generation

```
Input: DesignGuideline + task_id

Step 1: Stream Completes (line 650+)
┌─────────────────────────────────
│ Yield final chunk {
│   "status": "processing",
│   "stage": "handoff_to_generation",
│   "generation_task_id": "gen-uuid",
│   "status_endpoint": "GET /tasks/{gen_task_id}/status"
│ }
│
│ (Frontend saves generation_task_id for polling)
└─────────────────────────────────

Step 2: Backend Enqueues Stage C (logo_generate.py line 280+)
┌─────────────────────────────────
│ AIHubAsyncService.SubmitTask(
│   task_type="logo_generate_async",
│   input_args={
│     guideline=guideline,
│     task_id=task_id,
│     variation_count=4
│   }
│ )
│ → Task ID: "gen-abc123"
└─────────────────────────────────

Step 3: Status Polling Loop (logo_generate.py line 320+)
┌─────────────────────────────────
│ Loop: FE polls GET /tasks/{gen_task_id}/status
│
│ Response 1: { status: "pending", progress: 0 }
│ Response 2: { status: "processing", progress: 25 }
│ Response 3: { status: "processing", progress: 75 }
│ Response 4: { status: "completed", progress: 100,
│              result: { options: [...] } }
│
│ (Each call invokes GetTaskStatus from AI Hub)
└─────────────────────────────────
```

### Stage C: Parallel Image Generation (OptionGenerationService.generate)

```
Input: guideline, task_id, variation_count=4

Step 1: Create ThreadPoolExecutor (line 212)
┌─────────────────────────────────
│ with ThreadPoolExecutor(max_workers=4) as executor:  # Non-blocking parallelism
│     for i in range(4):
│         future = executor.submit(
│             _generate_single_option(i)
│         )
│     futures.append(future)
└─────────────────────────────────

Step 2: Per-Worker: Generate Single Option (line 148-185)
┌─────────────────────────────────
│ For each future:
│
│ a) Build Gemini prompt (line 46-77):
│    "Generate a logo with style=[...], colors=[...], 
│     concept=[...]. Output PNG."
│
│ b) Call Gemini Vision API (line 127):
│    response = gemini.generate_content(
│      model="gemini-2.0-flash",
│      contents=[prompt, binary_image_request]
│    )
│    → image_bytes (PNG)
│
│ c) Persist to Storage (line 118):
│    key = f"logos/{task_id}/option_{i}.png"
│    s3.upload(key, image_bytes)
│    → image_url = "https://cdn.../logos/{task_id}/option_0.png"
│
│ d) Return LogoOption:
│    LogoOption(
│      id=f"opt-{i}",
│      image_url=image_url,
│      concept=concepts[i]
│    )
└─────────────────────────────────

Step 3: Wait for All (line 213-220)
┌─────────────────────────────────
│ results = [future.result() for future in futures]
│ (Blocks until all 4 workers complete)
│ 
│ Typical timeline:
│ Worker 0: 3s
│ Worker 1: 4s
│ Worker 2: 3.5s
│ Worker 3: 4s  ← slowest
│ 
│ Total (parallel): 4s (not 3+4+3.5+4 = 14.5s sequential)
└─────────────────────────────────

Step 4: Return Results (line 223)
┌─────────────────────────────────
│ return [
│   LogoOption(..., url="/.../option_0.png"),
│   LogoOption(..., url="/.../option_1.png"),
│   LogoOption(..., url="/.../option_2.png"),
│   LogoOption(..., url="/.../option_3.png")
│ ]
└─────────────────────────────────

Step 5: Persist Final Output (logo_generate.py line 340+)
┌─────────────────────────────────
│ store.upsert(
│   session_id,
│   SessionContextState(
│     generated_option_ids=[...],
│     status="completed"
│   )
│ )
└─────────────────────────────────

Step 6: Return Completed Response (logo_generate.py line 345+)
┌─────────────────────────────────
│ return JobStatusResponse(
│   task_id=task_id,
│   status="completed",
│   progress_percent=100,
│   result=LogoGenerateOutput(
│     options=[...],
│     guideline=guideline,
│     required_field_state=state
│   )
│ )
│
│ FE receives complete response with all 4 image URLs
└─────────────────────────────────
```

---

## Data Flow & Context Management

### SessionContextStore (In-Memory CAS)

**File:** `source/context/session_store.py`

**Schema:**
```python
SessionContextState = {
    session_id: str,
    latest_brand_context: BrandContext | None,
    latest_guideline: DesignGuideline | None,
    required_field_state: RequiredFieldState,
    generated_option_ids: List[str],
    context_version: int  # ← Optimistic locking key
}
```

**Optimistic Locking (CAS Pattern):**

```python
def upsert(session_id, state, expected_context_version):
    with self._lock:
        if session_id not in self._store:
            self._store[session_id] = state
            return
        
        # CAS check: version must match
        if self._store[session_id].context_version != expected_context_version:
            raise ContextVersionConflictError(
                f"Conflict: expected v{expected_context_version}, "
                f"actual v{self._store[session_id].context_version}"
            )
        
        # Update & increment version
        self._store[session_id] = state
        state.context_version += 1
```

**Call Pattern:**
```python
# Read current version
prev_state = store.get(session_id)
prev_version = prev_state.context_version

# Merge & update
merged_context = merge_service.merge(...)
new_state = SessionContextState(
    latest_brand_context=merged_context,
    context_version=prev_version  # Pass expected version
)

# Write with CAS check
try:
    store.upsert(session_id, new_state, expected_context_version=prev_version)
except ContextVersionConflictError:
    # Concurrent update detected, retry from scratch
    retry_count += 1
    if retry_count < 3:
        return _retry_merge()
    else:
        raise ServiceError("Retry exhausted")
```

**Limitations & Concerns:**
- ⚠️ **In-memory only**: Lost on process restart
- ⚠️ **Single-process**: Requires sticky session in multi-worker setup
- ⚠️ **No TTL**: Sessions never expire (memory bloat over time)
- ⚠️ **No persistence**: Can't resume after outage

### Precedence Merge Logic

**File:** `source/services/context_merge_service.py`

**3-Tier Rule:**
```
Tier 1 (Explicit):   User provides in request body
Tier 2 (Extracted):  LLM extracted from query text
Tier 3 (Session):    Stored context from `session_id`

Rule: use first non-empty value
```

**Example Scenario:**

```yaml
Request:
  brand_name: "ACME Corp"       # Explicit ← WINS
  industry: null

Session (stored):
  brand_name: "OldCorp"
  industry: "fintech"

Extracted (LLM):
  brand_name: null
  industry: "finance"            # Extracted ← WINS (explicit is null)

Merge Result:
  brand_name: "ACME Corp"        # From explicit
  industry: "finance"            # From extracted (wins over session)
```

### Session Context Reuse Decision

**File:** `source/services/stream_intake_handler.py` (lines 140-207)

**Decision Tree:**

```
INPUT:
  use_session_context: bool
  previous_state: SessionContextState | None
  extracted: BrandContext (new query)
  query: str

REUSE SESSION IF:
═══════════════════════
  AND use_session_context == true
  AND previous_state exists
  AND NOT topic_swapped (industry changed)
  AND NOT generic_query
  AND (
    clarification_followup
    OR continuation_marker ("same", "again", "like before")
    OR explicit_required
    OR extracted_required
    OR same_topic_fallback
  )

REJECT SESSION IF:
═══════════════════════
  OR use_session_context == false
  OR no previous_state
  OR topic_swapped
  OR topic_mismatch (extracted ≠ session)
  OR generic_query_without_hints
```

**Continuation Markers (line 164-170):**
```python
CONTINUATIONS = {
    "same", "again", "continue", "as before", "like before", "reuse",
    "previous", "last", "nhu cu", "giong cu", "tiep", "tiep tuc",  # Vietnamese
    "giu nguyen"
}
```

**Topic Swap Detection (line 186-195):**
```python
if (extracted.industry and 
    previous.industry and
    extracted.industry != previous.industry):
    return "topic_swapped"  # User changed from fintech to sportswear
```

---

## Code Quality & Recommendations

### Issues Found

| Issue | Severity | File | Description |
|-------|----------|------|-------------|
| Unused import | ⚠️ Medium | `logo_generate.py` | `ProviderRoutingPolicy` imported but never used |
| Dead code | 🔴 High | `provider_routing_policy.py` | File exists but never called anywhere |
| Unnecessary class | ⚠️ Low | `async_payload_assembler.py` | Simple object builder, could be function |
| No duplicate logic | ✅ Good | All services | Clean separation of concerns |
| No deprecated code | ✅ Good | All services | No TODO/FIXME/XXX markers |

### Recommendations

#### 1. **Remove Dead Code** (Priority: HIGH)
```bash
# Action: Delete provider_routing_policy.py
# Remove from: source/services/__init__.py
# Update: logo_generate.py (line 28) to remove import

# Reason: Code not used, creates maintenance debt
```

#### 2. **Optimize AsyncPayloadAssembler** (Priority: LOW)
```python
# BEFORE (3-class file)
class AsyncPayloadAssembler:
    def build_completed(...):
        return JobStatusResponse(...)

# AFTER (inline as static functions)
def build_completed_response(task_id, result, ...):
    return JobStatusResponse(...)

def build_failed_response(task_id, error_code, ...):
    return JobStatusResponse(...)

# Or: Use Pydantic factory methods
LogoGenerateOutput.from_generator_result(...)
```

#### 3. **Add Session TTL** (Priority: MEDIUM)
```python
# SessionContextStore needs TTL to prevent memory bloat

# BEFORE (current)
self._store[session_id] = state  # Forever

# AFTER (with TTL)
self._store[session_id] = (state, time.time())  # Add timestamp

# Cleanup on get():
if time.time() - timestamp > 3600:  # 1 hour
    del self._store[session_id]
    raise SessionExpiredError
```

#### 4. **Consider Redis for Multi-Worker** (Priority: HIGH if scaling)
```python
# Current: SessionContextStore is single-process in-memory
# Problem: In multi-worker setup (K8s replicas), sessions lost on pod shift

# Option 1: Sticky session (not ideal)
# Option 2: Redis backend (recommended)

from redis import Redis

class RedisSessionStore(SessionContextStore):
    def __init__(self):
        self.redis = Redis(host="localhost")
    
    def get(self, session_id):
        data = self.redis.get(f"session:{session_id}")
        if not data:
            return None
        return SessionContextState.parse_raw(data)
    
    def upsert(self, session_id, state, expected_version):
        # Use Redis WATCH/MULTI/EXEC for CAS
        ...
```

#### 5. **Make design.md Write Async** (Priority: MEDIUM)
```python
# Current: design_memory.persist() is blocking

# After (non-blocking)
async def persist_async(self, ...):
    # Queue to background task
    self._task_queue.put({
        "topic": topic,
        "record": record
    })
    return  # Immediate return

# Background worker:
async def _background_writer():
    while True:
        item = await self._task_queue.get()
        self._write_to_file(item)
```

#### 6. **Add Event Sourcing** (Priority: LOW, optional)
```python
# For better auditability & analytics

# New table: events
CREATE TABLE events (
  id BIGSERIAL PRIMARY KEY,
  session_id VARCHAR,
  timestamp TIMESTAMP,
  event_type VARCHAR,  -- "context_merged", "guideline_inferred", ...
  old_state JSONB,
  new_state JSONB,
  metadata JSONB
);

# Usage in StreamIntakeHandler:
_emit_event({
  event_type="context_merged",
  session_id=session_id,
  old_state=prev_context,
  new_state=merged_context
})
```

---

## Service File Usage Matrix

| File | Purpose | Used In | Status | Recommendation |
|------|---------|---------|--------|-----------------|
| `stream_intake_handler.py` | Stage A/B orchestrator | logo_generate.stream() | ✅ Core | Keep |
| `llm_logo_tools.py` | LLM tools | StreamIntakeHandler | ✅ Core | Keep |
| `option_generation_service.py` | Stage C image gen | logo_generate.async_generate() | ✅ Core | Keep |
| `context_merge_service.py` | 3-tier merge | StreamIntakeHandler | ✅ Core | Keep |
| `required_field_gate.py` | Validation | StreamIntakeHandler | ✅ Core | Keep |
| `guideline_inference_service.py` | Guideline rules | StreamIntakeHandler | ✅ Core | Keep |
| `web_research_service.py` | Web search | StreamIntakeHandler | ✅ Core | Keep |
| `design_memory_service.py` | Audit trail | StreamIntakeHandler | ✅ Core | Keep (async write) |
| `lifecycle_status_manager.py` | State machine | logo_generate | ✅ Core | Keep |
| `async_payload_assembler.py` | Response builder | logo_generate | ✅ Used | Inline or extract |
| `provider_routing_policy.py` | Provider fallback | **NONE** | ❌ Dead | **DELETE** |

---

## Summary

### Code Organization: ✅ **GOOD**
- 9/12 services are actively used and serve clear purposes
- Single Responsibility Principle respected
- No duplicate logic detected
- Flow is natural (intake → merge → gate → research → guideline → generation)

### Progress Mapping: ✅ **STATUS-BASED (NOT progress=5)**
- Progress uses StatusEnum: pending(0%) → processing(50%) → completed(100%)
- No intermediate values unless explicit_progress provided
- To show granular progress, would need per-stage metadata

### Actionable Issues:
1. **🔴 HIGH:** Remove `provider_routing_policy.py` (dead code)
2. **🟡 MEDIUM:** Add session TTL to prevent memory bloat
3. **🟡 MEDIUM:** Make design.md writes async to avoid stream latency
4. **⚠️ LOW:** Inline AsyncPayloadAssembler or use Pydantic factories

### Production Readiness:
- ✅ Core logic is solid and well-structured
- ⚠️ Session store needs Redis for multi-worker deployments
- ⚠️ No session expiration (memory leak over time)
- ✅ Optimistic locking (CAS) prevents data corruption
- ✅ Fallback mechanisms in place (LLM providers, research)

---

## Glossary of Terms

- **CAS**: Compare-and-Swap (optimistic locking)
- **Stage A**: Intake & clarification (query extraction, required field validation)
- **Stage B**: Guideline inference (design rules generation)
- **Stage C**: Image generation (parallel Gemini calls, storage)
- **Sticky Session**: Same user request always routed to same server
- **TTL**: Time-To-Live (auto-cleanup after timeout)
- **ThreadPoolExecutor**: Non-async parallelism (blocks on `.result()`)
- **ResearchContext**: Web search insights (design trends, references)
- **DesignGuideline**: Structured design rules (style, colors, icons, fonts, constraints)

