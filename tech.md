# Source Architecture Summary - Logo Design Full Flow (As-Built)

Tai lieu nay mo ta duy nhat flow dang chay that trong code hien tai sau khi da clean path du.
Muc tieu: doc 1 lan de hieu he thong chay nhu the nao, file nao giu logic gi, va call path cu the di qua dau.

## 1. Tong quan nhanh

Flow hien tai la stream-first, chay tron bo Stage A -> Stage B -> Stage C trong mot request stream:

1. UI tao `LogoGenerateInput` va goi `LogoGenerateTask.stream_process()`.
2. Task chuyen input sang planner.
3. Planner dieu phoi Stage A worker (intake/gate).
4. Neu thieu required fields thi dung o clarification.
5. Neu pass gate thi chay Stage B worker (research + guideline).
6. Sau guideline thi chay Stage C worker (generate option theo stream).
7. Cuoi cung tra chunk `completed` voi payload day du.

Luu y quan trong:

- Stage B da la async-only trong runtime hien tai.
- Nhung sync path cu cua Stage B da duoc bo.
- Planner khong con flag include_generation trong full flow hien tai, Stage C la path mac dinh.

## 2. End-to-end call path chi tiet

### 2.1 Tu UI den task

- `streamlit_logo_design.py` tao input:
  - `LogoGenerateInput(session_id, query, references, variation_count)`
- UI goi:
  - `LogoGenerateTask.stream_process(...)`

### 2.2 Task adapter

- `source/tasks/logo_generate.py`
- Vai tro:
  - Khoi tao singleton dependency (`initialize()`)
  - Build planner qua `build_logo_generate_planner(...)`
  - Stream tung chunk planner tra ve
  - Neu fail thi map sang output failed chunk

Call path:

- `stream_process()`
  - tao `request_body`
  - `async for chunk in self._planner.iter_chunks(request_body)`
  - wrap thanh `LogoGenerateTaskOutput`

### 2.3 Planner orchestration

- `source/orchestration/planner/logo_generate_planner.py`
- Vai tro:
  - Dieu phoi thu tu stage
  - Khong xu ly nghiep vu nang
  - Emit processing/failed/completed chunk qua observer

Call path trong `iter_chunks()`:

1. Parse input + lay previous session state.
2. Emit intake chunk.
3. `await self._stage_a_worker.run(...)`.
4. Neu not logo intent hoac gate fail -> emit clarification chunk + return.
5. Emit web_research_started.
6. `await self._stage_b_worker.run(...)`.
7. Emit web_research_completed + guideline_completed.
8. `async for chunk in self._stage_c_worker.iter_chunks(...)`.

## 3. Stage A chi tiet

### 3.1 Worker

- `source/workers/stage_a_worker.py`
- Vai tro:
  - Intent detect
  - Extract + reference analysis song song
  - Merge explicit fields + extracted + session fallback
  - Required-field gate (`brand_name`, `industry`)
  - Persist checkpoint clarification neu gate fail

### 3.2 Toolset va runtime

- `source/services/stage_a/toolset.py`
- `source/services/stage_a/llm_runtime.py`

Diem chinh:

- Toolset hien tai dung async methods trong full flow:
  - `detect_intent_async(...)`
  - `extract_inputs_async(...)`
  - `analyze_references_async(...)`
  - `build_clarification_questions_async(...)`
  - `infer_guideline_async(...)`
- Runtime helper dung async path JSON tool call.

### 3.3 Checkpoint helper

- `source/services/stage_a/checkpoint.py`
- Vai tro:
  - `persist_with_cas(...)`
  - upsert state theo `context_version`
  - retry conflict de tranh stale write

## 4. Stage B chi tiet (async-only)

### 4.1 Worker

- `source/workers/stage_b_worker.py`
- Call path:
  - `await self._web_research_service.run_async(...)`
  - enrich optional fields neu context con thieu
  - `await self._toolset.infer_guideline_async(...)`
  - persist checkpoint guideline + research context

### 4.2 Web research service

- `source/services/stage_b/web_research_service.py`
- Path chinh:
  - `run_async(...)`
    - build queries
    - `asyncio.gather` goi `search_async` cho tung query
    - `_finalize_context_async(...)`
      - dedupe source/image
      - `_select_fetchable_images_async(...)`
      - `await self._gemini.analyze_async(...)`
      - build `ResearchContext`

### 4.3 External clients

- `source/services/stage_b/research_clients.py`
- Vai tro:
  - `search_async(query)` goi SerpAPI
  - `can_fetch_image_async(image_url)` probe URL anh

Image fetchability policy hien tai:

- uu tien HEAD check
- fallback GET stream de check header
- chi can status + content-type image
- khong download full body o buoc can_fetch

### 4.4 Gemini analyzer

- `source/services/stage_b/gemini_analyzer.py`
- Vai tro:
  - Download image bytes async
  - Gui multimodal request cho Gemini
  - Parse JSON output
  - Aggregate market analysis + strategic directions + extracted signals

Path chinh:

- `analyze_async(...)`
  - tao tasks `_analyze_single_image_async(...)`
  - `await asyncio.gather(*tasks)`
  - `_aggregate_analysis_rows(...)`

Luu y:

- Sync path cu da duoc bo.
- Full flow hien tai chi dung async methods.

## 5. Stage C chi tiet

### 5.1 Worker

- `source/workers/stage_c_worker.py`
- Vai tro:
  - validate guideline checkpoint
  - emit `generation_started`
  - stream tung `generation_option_ready`
  - assemble completed payload

### 5.2 Generator

- `source/services/stage_c/generator.py`
- Vai tro:
  - build prompt option theo concept variant
  - goi Gemini image generation
  - persist asset
  - tra `LogoOption`

Parallel path:

- `iter_generate_async(...)`
  - tao list task qua `asyncio.to_thread(...)`
  - consume theo `asyncio.as_completed(...)`

Hanh vi UI chunk:

- Option nao xong truoc se phat chunk truoc.
- Nen 1/3, 2/3, 3/3 la stream incremental dung thiet ke.

## 6. Observer + Shared services

### 6.1 Observer

- `source/orchestration/observer/stream_observer.py`
- Vai tro:
  - tao payload processing/completed/failed
  - chuan hoa metadata stage
  - tach error code/message

- `source/orchestration/observer/error_mapper.py`
  - helper tach prefix error dang `CODE: message`

### 6.2 Shared

- `source/services/shared/lifecycle_status.py`
  - `LifecycleStatusManager`
  - map status -> progress
  - build `JobStatusResponse`

- `source/services/shared/payload_assembler.py`
  - `AsyncPayloadAssembler`
  - build completed payload
  - build failed payload

## 7. Session state va schema layer

### 7.1 Session context

- `source/context/session_store.py`
- Class:
  - `SessionContextStore`
  - `ContextVersionConflictError`

Dung trong full flow:

- `get(session_id)` de resume clarification
- `upsert(state, expected_context_version=...)` de CAS-safe checkpoint

### 7.2 Schema

- `source/schemas/domain.py`
  - `LogoGenerateInput` (TaskInputBaseModel)
  - `BrandContext`, `RequiredFieldState`, `DesignGuideline`, `ResearchContext`, `LogoOption`, `LogoGenerateOutput`
- `source/schemas/api.py`
  - status/request payload contracts
- `source/schemas/status.py`
  - `SessionContextState`

## 8. UI Streamlit hien tai va latency notes

- File: `streamlit_logo_design.py`

Flow UI:

1. Tao input + references tu text, upload, URL.
2. Goi async task stream qua `_run_chat_turn(...)`.
3. Moi chunk cap nhat:
  - timeline
  - thinking text
  - progress
  - gallery/canvas

Cac diem da clean de giam latency web-search rendering:

- Giam render lai reference gallery trong luc stream:
  - chi render khi doi stage va stage nam trong nhom can preview.
- Giam so card preview reference:
  - user refs va web refs deu limit 3.
- Don gian hoa remote image fetch:
  - dung 1 HTTPX pass timeout ngan hon.
  - bo fallback urllib de tranh wait keo dai trong UI loop.

## 9. Danh sach file quan trong nhat can doc truoc

Neu muon onboard nhanh, nen doc theo thu tu:

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

## 10. Ket luan ky thuat

1. Full flow hien tai la async stream end-to-end trong mot task execution.
2. Stage B la async-only path; sync path cu da duoc clean.
3. Stage C van parallel generation va stream incremental dung semantics.
4. Architecture hien tai de doc va trace call path ro rang hon sau khi bo path du.
