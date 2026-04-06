# Source Architecture Summary - Full Flow trong `source`

Tai lieu nay chi tap trung vao module `source`, mo ta ro:

1. Full flow chay nhu the nao.
2. File nao chua ham gi trong full flow.
3. Moi file quan trong dong vai tro gi.
4. Vi du case cu the de de hinh dung.

## 1. Full flow tong quan (chay that trong code hien tai)

Flow hien tai la stream end-to-end:

1. UI tao `LogoGenerateInput`.
2. UI goi `LogoGenerateTask.stream_process(...)`.
3. Task day request vao planner.
4. Planner chay Stage A -> Stage B -> Stage C.
5. Moi stage emit chunk theo thoi gian thuc.
6. Ket thuc bang chunk `completed` chua output cuoi.

Luu y quan trong:

- Stage B hien tai la async-only.
- Stage C van chay parallel cho generate option.
- Session context duoc luu trong memory de clarification follow-up.

## 2. Call path cu the theo file/ham

### 2.1 Entry point task

File: `source/tasks/logo_generate.py`

Ham quan trong:

- `LogoGenerateTask.initialize()`:
  - Tao `SessionContextStore`, `LifecycleStatusManager`.
  - Tao `LogoDesignToolset`, `WebResearchService`, `OptionGenerationService`.
  - Build planner qua `build_logo_generate_planner(...)`.

- `LogoGenerateTask.stream_process(...)`:
  - Nhan `LogoGenerateInput`.
  - Tao `request_body`.
  - `async for chunk in self._planner.iter_chunks(request_body)`.
  - Wrap tung chunk thanh `LogoGenerateTaskOutput`.

Tac dung:

- Day la adapter voi ai_hub_sdk, khong xu ly nghiep vu logo o day.

### 2.2 Planner dieu phoi

File: `source/orchestration/planner/logo_generate_planner.py`

Ham quan trong:

- `iter_chunks(request_body)`:
  - Parse input.
  - Lay previous context trong session store.
  - Emit chunk intake.
  - `await stage_a_worker.run(...)`.
  - Neu fail gate thi emit clarification + dung.
  - Neu pass gate thi emit web_research_started.
  - `await stage_b_worker.run(...)`.
  - Emit web_research_completed + guideline_completed.
  - `async for chunk in stage_c_worker.iter_chunks(...)`.

Tac dung:

- Dieu phoi thu tu stage.
- Map exception thanh failed chunk qua observer.
- Khong chua logic LLM hay logic research chi tiet.

### 2.3 Observer stream payload

File: `source/orchestration/observer/stream_observer.py`

Ham quan trong:

- `processing(...)`
- `failed_from_exception(...)`

Tac dung:

- Chuan hoa payload chunk (`status`, `progress_percent`, `metadata`, `error_code`, `error_message`).

File: `source/orchestration/observer/error_mapper.py`

- `split_error_code_message(...)` de tach `CODE: message`.

## 3. Stage A - Intake/Gate

### 3.1 Worker Stage A

File: `source/workers/stage_a_worker.py`

Ham quan trong:

- `run(input_data, previous)`

Logic:

1. Goi intent detect.
2. Chay song song:
  - extract input tu query
  - phan tich reference image
3. Merge context:
  - explicit field tu request
  - extracted field tu model
  - fallback tu previous session neu la clarification follow-up
4. Gate required fields (`brand_name`, `industry`).
5. Neu fail gate, persist checkpoint de lan sau resume.

### 3.2 Toolset Stage A

File: `source/services/stage_a/toolset.py`

Cac ham full flow dung:

- `detect_intent_async(...)`
- `extract_inputs_async(...)`
- `analyze_references_async(...)`
- `build_clarification_questions_async(...)`
- `infer_guideline_async(...)`

Tac dung:

- Day la noi dong goi prompt va parse output cho domain logo.

### 3.3 Runtime helper Stage A

File: `source/services/stage_a/llm_runtime.py`

Ham quan trong:

- `_call_json_tool_async(...)`

Tac dung:

- Goi LLM async, ep output ve JSON object/list, throw `ToolExecutionError` neu payload loi.

### 3.4 CAS checkpoint helper

File: `source/services/stage_a/checkpoint.py`

Ham quan trong:

- `persist_with_cas(...)`

Tac dung:

- Ghi state theo `context_version` de tranh stale write.

## 4. Stage B - Research + Guideline (async-only)

### 4.1 Worker Stage B

File: `source/workers/stage_b_worker.py`

Ham quan trong:

- `run(...)`

Logic:

1. Xac dinh optional fields con thieu (`style/color/symbol/typography`).
2. Goi `await web_research_service.run_async(...)`.
3. Enrich context tu research output neu con thieu field.
4. Goi `await toolset.infer_guideline_async(...)`.
5. Persist checkpoint gom context + guideline + research context.

### 4.2 WebResearchService

File: `source/services/stage_b/web_research_service.py`

Ham quan trong:

- `run_async(context, requested_optional_fields)`
- `_select_fetchable_images_async(...)`
- `_finalize_context_async(...)`

Logic chi tiet:

1. Build query list tu context.
2. `asyncio.gather` goi SerpAPI cho moi query.
3. Gop ket qua, dedupe sources/images.
4. Loc top image fetchable.
5. Goi Gemini analyzer async.
6. Build `ResearchContext` (queries, top_images, market_analysis, strategic_directions, takeaways, citations).

### 4.3 Research client

File: `source/services/stage_b/research_clients.py`

Ham quan trong:

- `search_async(query)`
- `can_fetch_image_async(image_url)`

Logic image fetchability:

1. Thu `HEAD` truoc.
2. Neu host khong support thi fallback `GET` stream.
3. Chi check header status + content-type image.
4. Khong download full body o buoc can_fetch.

### 4.4 Gemini analyzer

File: `source/services/stage_b/gemini_analyzer.py`

Ham quan trong:

- `analyze_async(...)`
- `_analyze_single_image_async(...)`
- `_download_image_bytes_async(...)`
- `_aggregate_analysis_rows(...)`

Logic:

1. Moi image duoc analyze rieng.
2. Download bytes that su cho buoc multimodal.
3. Goi Gemini va parse JSON.
4. Tong hop thanh ket qua cuoi Stage B.

Luu y:

- Sync path Stage B da duoc bo trong code hien tai.

## 5. Stage C - Generate option

### 5.1 Worker Stage C

File: `source/workers/stage_c_worker.py`

Ham quan trong:

- `iter_chunks(task_id, input_args)`

Logic:

1. Lay guideline da checkpoint.
2. Emit `generation_started`.
3. `async for option in option_generation_service.iter_generate_async(...)`.
4. Moi option emit 1 chunk `generation_option_ready`.
5. Cuoi cung assemble payload completed.

### 5.2 Generator

File: `source/services/stage_c/generator.py`

Ham quan trong:

- `iter_generate_async(...)`
- `_generate_single_option(...)`

Logic parallel:

1. Tao task bang `asyncio.to_thread(...)` cho tung concept.
2. Consume theo `asyncio.as_completed(...)`.
3. Option nao xong truoc emit truoc.

Y nghia voi UI:

- Timeline 1/3 -> 2/3 -> 3/3 la dung theo stream incremental.

## 6. Shared va session context

### 6.1 Shared status/payload

File: `source/services/shared/lifecycle_status.py`

- `LifecycleStatusManager`:
  - `resolve_progress(...)`
  - `build_status_response(...)`

File: `source/services/shared/payload_assembler.py`

- `AsyncPayloadAssembler`:
  - Build payload completed/failed cho output cuoi.

### 6.2 Session store

File: `source/context/session_store.py`

Cac ham full flow dung:

- `get(session_id)`
- `upsert(state, expected_context_version=...)`

Tac dung:

- Luu checkpoint clarification/guideline trong memory.

## 7. Vi du case cu the de de hieu

Case:

- User nhap: "Thiet ke logo cho Lumi Cafe, phong cach toi gian, tong mau nau kem."

Flow:

1. Stage A:
  - detect intent -> logo request.
  - extract duoc `brand_name=Lumi Cafe`, `industry=cafe`.
  - gate pass vi du required fields.

2. Stage B:
  - build query trend/logo cafe.
  - search async nhieu query.
  - loc top image fetchable.
  - analyze async tung image bang Gemini.
  - infer guideline tu context + research.

3. Stage C:
  - generate 3 options song song.
  - UI nhan chunk option theo thu tu hoan thanh (khong nhat thiet theo seed).
  - assembler tra completed payload.

## 8. Danh sach file nen doc theo thu tu

Neu onboard nhanh, nen doc theo thu tu sau:

1. `source/tasks/logo_generate.py`
2. `source/orchestration/planner/logo_generate_planner.py`
3. `source/workers/stage_a_worker.py`
4. `source/workers/stage_b_worker.py`
5. `source/workers/stage_c_worker.py`
6. `source/services/stage_b/web_research_service.py`
7. `source/services/stage_b/research_clients.py`
8. `source/services/stage_b/gemini_analyzer.py`
9. `source/services/stage_c/generator.py`
10. `source/context/session_store.py`

## 9. Ket luan

1. Full flow trong `source` hien tai da ro rang theo Task -> Planner -> Workers -> Services.
2. Stage B la async-only va da bo path du sync.
3. Stage C stream incremental + parallel generation dung semantics.
4. Viec trace loi va review code se de hon neu bam theo call path trong tai lieu nay.
