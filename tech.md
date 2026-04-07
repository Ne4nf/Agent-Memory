# Plan: Clean Tool Architecture + Logo Design Pipeline

## Summary

Refactor ai_hub_sdk tools/schemas to support **Logo Design Pipeline**:

### Full Flow: POST /internal/v1/tasks/stream
```
User Request 
  → Stage A (Intake & Clarification)
    → IntentDetectTool → InputExtractionTool → ReferenceImageAnalyzeTool 
    → ContextMerge → RequiredFieldGate 
    → [if missing] ClarificationLoopTool (loop back to merge)
  → Stage B (Research & Guideline)
    → WebResearchService → FetchableImageSelector → GeminiResearchAnalyzer → DesignInferenceTool
  → Stage C (Generation)
    → OptionGenerationService (parallel) → StoragePersistence
  → Stream completed chunks progressively
```

### Implementation Goals
1. **Tool wrappers** — wrap Stage A/B/C tools in clean BaseTool subclasses
2. **Tool context** — metadata for planner (name, description, input/output schemas)
3. **DAG planner** — generates Stage-ordered DAG (A → B → C with gate logic)
4. **Stream executor** — executes DAG, yields results after each stage/task
5. **Clean imports** — `from ai_hub_sdk.tools import IntentDetectTool, WebResearchService, ...`

**Approach**: Extend existing BaseTool + ToolContextManager → build Stage-aware planner → stream results per stage completion.

---

## Phases & Steps

### Phase 1: Foundation - Tool Wrappers + Context (Parallel-capable)

**Goal**: Wrap existing/new logo design tools in clean BaseTool classes + build metadata system.

1. **Create `ToolContext` schema** [ai_hub_sdk/schemas/tool_context.py]
   - Model: `name`, `description`, `input_schema` (JSON), `output_schema` (JSON), `stage` (A/B/C), `category` (detect/extract/research/generate)
   - Method: `@classmethod from_tool(tool: BaseTool)` to auto-extract

2. **Extend `BaseTool`** [ai_hub_sdk/tools/base.py]
   - Add attributes: `stage: Literal["A", "B", "C"]`, `category: str`
   - Add method: `to_context() -> ToolContext`
   - Ensure: name, description always required

3. **Create `ToolContextManager`** [ai_hub_sdk/tools/context_manager.py]
   - Registry: `register(tool, stage)`, `get_by_stage(stage) -> List[ToolContext]`
   - Build: `build_contexts(tools) -> Dict[str, ToolContext]` (keyed by name)
   - Export: `to_llm_format() -> Dict` (OpenAI format)

4. **Create Stage A tools** [ai_hub_sdk/tools/stage_a/]
   - `intent_detect.py`: `IntentDetectTool` (detect intent: logo/banner/icon)
   - `input_extraction.py`: `InputExtractionTool` (parse query for brand_name, industry, colors, etc)
   - `reference_image_analyzer.py`: `ReferenceImageAnalyzeTool` (analyze uploaded reference images via Gemini)
   - `context_merger.py`: `ContextMergerTool` (merge explicit input → extracted → session context)
   - `required_field_gate.py`: `RequiredFieldGateTool` (validate brand_name + industry present)
   - `clarification_loop.py`: `ClarificationLoopTool` (LLM asks user for missing fields)

5. **Create Stage B tools** [ai_hub_sdk/tools/stage_b/]
   - `web_research_service.py`: `WebResearchService` (search web for design trends)
   - `fetchable_image_selector.py`: `FetchableImageSelector` (filter searchable images)
   - `gemini_research_analyzer.py`: `GeminiResearchAnalyzer` (analyze image bytes + research)
   - `design_inference_tool.py`: `DesignInferenceTool` (infer design guidelines from research)

6. **Create Stage C tools** [ai_hub_sdk/tools/stage_c/]
   - `option_generation_service.py`: `OptionGenerationService` (generate N design options, parallel)
   - `storage_persistence.py`: `StoragePersistenceTool` (persist results to DB)

7. **Test tool extraction** (unit tests)
   - Verify `ToolContext` for each tool
   - Schemas correct
   - Stage + category tagged properly

### Phase 2: DAG Schema + Stage-Aware Planner (Depends on Phase 1)

**Goal**: Define DAG structure for stage pipeline, build planner that generates it.

8. **Create DAG schemas** [ai_hub_sdk/schemas/pipeline_dag.py]
   - `TaskNode`: `id`, `name`, `tool_name`, `stage`, `tool_input`, `metadata`
   - `StageGroup`: `stage` (A/B/C), `tasks: List[TaskNode]`, `parallel` (bool)
   - `PipelineDAG`: `stages: List[StageGroup]`, `dependencies`, `execution_order`
   - Logic: Stage A → B → C (sequential), but within stage can parallelize

9. **Create `LogoPlannerTool`** [ai_hub_sdk/tools/logo_planner.py]
   - Inherits: `BaseTool`
   - Input: query, uploaded_images, session_context, available_tools
   - Output: `PipelineDAG`
   - Implementation:
     - OpenAI GPT-4o structured output
     - System: "You are a logo design planner. Create execution plan: Stage A (intake/clarify) → Stage B (research/analyze) → Stage C (generate options)"
     - Ensure: A always has RequiredFieldGate before B
     - If missing fields detected → include ClarificationLoopTool in stage A

10. **Test Planner** (integration test)
    - Query: "create logo for tech startup Acme, modern style"
    - Expected: DAG with Stage A complete, B ready, C queued
    - Verify: task IDs, tool names, gate logic correct

### Phase 3: Pipeline Executor + Streaming (Depends on Phase 2)

**Goal**: Execute DAG by stage, stream results progressively.

11. **Create `PipelineExecutor`** [ai_hub_sdk/core/task/pipeline_executor.py]
    - Input: `PipelineDAG`, `tool_registry: Dict[str, BaseTool]`, `session_context`
    - Execution: 
      - Stage A: run sequential (intent → extract → analyze → merge → validate; loop if gate fails)
      - Stage B: run sequential (research → select → analyze → infer)
      - Stage C: run parallel (generate N options, persist all)
    - Output: `AsyncGenerator[StageEvent]`

12. **Create event schemas** [ai_hub_sdk/schemas/pipeline_events.py]
    - `StageStarted(stage, task_count)`
    - `TaskStarted(task_id, task_name)`
    - `TaskCompleted(task_id, result)`
    - `GateFailed(required_fields)` → triggers clarification
    - `StageCompleted(stage, all_results)`
    - `PipelineCompleted(final_output, designs)`
    - `ProcessingError(error)`

13. **Integrate streaming** (async generator)
    - Runner: `async def run_logo_pipeline(query, context) → AsyncGenerator[PipelineEvent]`:
      - 1. Load tool registry
      - 2. Call LogoPlannerTool → PipelineDAG
      - 3. Yield: `PipelineStarted(dag)`
      - 4. Execute stage by stage:
         - a. Yield: `StageStarted(A)`
         - b. For each task: yield TaskStarted → execute → yield TaskCompleted
         - c. Handle GateFailed → loop/clarify
         - d. Yield: `StageCompleted(A, results)`
      - 5. Final: `PipelineCompleted(results)`

### Phase 4: Clean Exports + Docs (Depends on Phase 3)

**Goal**: Easy imports + usage guide.

14. **Update exports** [ai_hub_sdk/tools/__init__.py, ai_hub_sdk/schemas/__init__.py]
    - Tools: stage A/B/C tools + LogoPlannerTool
    - Schemas: ToolContext, PipelineDAG, StageGroup, TaskNode, all Events

15. **Write Vietnamese guide** [docs/guides/tools/logo_pipeline_vi.md]
    - Architecture overview
    - Flow diagram (Stage A → B → C)
    - Each tool's role
    - How to extend

16. **Write English guide** [docs/guides/tools/logo_pipeline.md]
    - Same as above, English

17. **Code example** [examples/logo_pipeline_demo.ipynb]
    - Minimal: load tools → run query → stream results
    - Advanced: custom tool + DAG inspection + event handling

### Phase 5: Testing + Validation

**Goal**: Ensure architecture + backward compatibility.

18. **Unit tests** [tests/unit/tools/]
    - ToolContext extraction per tool
    - Tool registry by stage
    - DAG schema validation
    - Event schemas serialization

19. **Integration tests** [tests/integration/]
    - Full pipeline (mock tools) query → plan → execute
    - Gate logic: missing fields → clarification → retry
    - Stage transitions + streaming events
    - Agent unchanged (backward compat)

20. **Manual e2e test**
    - Real query: "logo for tech company, blue + modern style"
    - Check: plan generated → stages executed → options streamed

---

## Relevant Files

**To Create:**

**Schemas:**
- `ai_hub_sdk/schemas/tool_context.py` — ToolContext with stage + category
- `ai_hub_sdk/schemas/pipeline_dag.py` — TaskNode, StageGroup, PipelineDAG
- `ai_hub_sdk/schemas/pipeline_events.py` — StageStarted, TaskStarted, TaskCompleted, GateFailed, StageCompleted, PipelineCompleted, ProcessingError

**Tools - Stage A:**
- `ai_hub_sdk/tools/stage_a/__init__.py`
- `ai_hub_sdk/tools/stage_a/intent_detect.py` — IntentDetectTool
- `ai_hub_sdk/tools/stage_a/input_extraction.py` — InputExtractionTool
- `ai_hub_sdk/tools/stage_a/reference_image_analyzer.py` — ReferenceImageAnalyzeTool
- `ai_hub_sdk/tools/stage_a/context_merger.py` — ContextMergerTool
- `ai_hub_sdk/tools/stage_a/required_field_gate.py` — RequiredFieldGateTool
- `ai_hub_sdk/tools/stage_a/clarification_loop.py` — ClarificationLoopTool

**Tools - Stage B:**
- `ai_hub_sdk/tools/stage_b/__init__.py`
- `ai_hub_sdk/tools/stage_b/web_research_service.py` — WebResearchService
- `ai_hub_sdk/tools/stage_b/fetchable_image_selector.py` — FetchableImageSelector
- `ai_hub_sdk/tools/stage_b/gemini_research_analyzer.py` — GeminiResearchAnalyzer
- `ai_hub_sdk/tools/stage_b/design_inference_tool.py` — DesignInferenceTool

**Tools - Stage C:**
- `ai_hub_sdk/tools/stage_c/__init__.py`
- `ai_hub_sdk/tools/stage_c/option_generation_service.py` — OptionGenerationService
- `ai_hub_sdk/tools/stage_c/storage_persistence.py` — StoragePersistenceTool

**Core:**
- `ai_hub_sdk/tools/logo_planner.py` — LogoPlannerTool (stage-aware)
- `ai_hub_sdk/tools/context_manager.py` — ToolContextManager (by stage)
- `ai_hub_sdk/core/task/pipeline_executor.py` — PipelineExecutor (stage-sequential, task-parallel)

**Docs & Examples:**
- `docs/guides/tools/logo_pipeline_vi.md` — Vietnamese guide (CHI TIẾT)
- `docs/guides/tools/logo_pipeline.md` — English guide
- `examples/logo_pipeline_demo.ipynb` — Full flow demo

**To Modify:**
- `ai_hub_sdk/tools/base.py` — Add `stage`, `category` attributes + `to_context()` method
- `ai_hub_sdk/schemas/__init__.py` — Export new schemas
- `ai_hub_sdk/tools/__init__.py` — Export all stage tools + planner + context manager

---

## Verification

1. **Tools wrap correctly**: Each stage tool instantiates, schema exports valid
2. **ToolContextManager**: Registry by stage works, exports to OpenAI format
3. **LogoPlannerTool**: Query → PipelineDAG with stage structure
4. **PipelineExecutor**: DAG executes stage-by-stage, events streamed
5. **Gate logic**: Missing required_fields → ClarificationLoopTool triggered → retry
6. **Streaming**: Events flow properly (StageStarted → TaskStarted → TaskCompleted → StageCompleted)
7. **Backward compat**: Existing Agent + tools unaffected

---

## Decisions & Scope

**Included:**
- Tool wrappers for Stage A/B/C (logo design)
- Tool context + stage + category tagging
- Stage-aware DAG + planner
- Pipeline executor with streaming events
- Gate logic (validation + clarification loop)
- Clean imports

**Excluded:**
- Observer/monitoring → add later
- Parallel task execution (within stage parallelizable, between stages sequential)
- Result aggregation beyond events → keep simple
- SQLite/DB integration → persist results only
- Custom agent framework changes

**Key Assumptions:**
1. OpenAI API available for LogoPlannerTool + LLM calls
2. Gemini API available for image analysis (Stage B)
3. Web search API available (Stage B)
4. Tools are deterministic (no circular gate failures)
5. Each stage output feeds next stage input automatically

---

## Timeline

- **Phase 1**: ~1h (6-7 tools + schemas)
- **Phase 2**: ~30min (DAG + planner)
- **Phase 3**: ~45min (executor + events)
- **Phase 4**: ~45min (exports + docs + notebook)
- **Phase 5**: ~30min (tests)
- **Total**: ~3.5 hours focused work
