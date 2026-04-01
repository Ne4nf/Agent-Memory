# Source Full Flow and File Map

## 1. Muc tieu tai lieu
Tai lieu nay mo ta day du luong xu ly va vai tro cua tung file trong thu muc `source/`, dong thoi tong hop nhanh cac diem duplicate hoac dau hieu logic cu.

## 2. Tong quan cau truc source

```text
source/
  __init__.py
  config.py
  logger.py
  context/
    __init__.py
    session_store.py
  schemas/
    __init__.py
    models.py
  services/
    __init__.py
    async_payload_assembler.py
    context_merge_service.py
    design_memory_service.py
    guideline_inference_service.py
    lifecycle_status_manager.py
    llm_logo_tools.py
    option_generation_service.py
    provider_routing_policy.py
    required_field_gate.py
    stream_intake_handler.py
    web_research_service.py
  tasks/
    __init__.py
    logo_generate.py
```

## 3. Entry point va dependency wiring
- Entry point runtime thuc te cho business flow la `LogoGenerateTask` trong `source/tasks/logo_generate.py`.
- `LogoGenerateTask.initialize()` khoi tao singleton service graph:
  - `SessionContextStore`
  - `LifecycleStatusManager`
  - `OptionGenerationService`
  - `AsyncPayloadAssembler`
  - `StreamIntakeHandler` + cac dependency ben trong (`ContextMergeService`, `RequiredFieldGateService`, `LogoDesignToolset`, `WebResearchService`, `DesignMemoryService`).
- Thu muc `source/api/` hien dang trong (khong co module API ben trong source).

## 4. Luong xu ly end-to-end

### 4.1 Stream mode (`stream_process`)
Muc tieu: xu ly Stage A/B theo chunk realtime, sau do chay Stage C va stream tien trinh.

1. Nhap request va chuyen thanh `LogoGenerateInput`.
2. Goi `StreamIntakeHandler.iter_chunks()` de chay Stage A/B:
   - Intent detection (logo hay khong)
   - Input extraction + image reference analysis
   - Session merge
   - Required-field gate (brand_name, industry)
   - Clarification neu thieu truong bat buoc
   - Web research (SerpAPI + Gemini multimodal)
   - Guideline inference
   - Persist checkpoint vao session store (CAS) + append snapshot vao `design.md`
3. Neu Stage A/B completed thi vao Stage C trong `stream_process`:
   - Phat chunk `generation_started`
   - Goi `OptionGenerationService.generate()`
   - Stream tung option
   - Dong goi payload final qua `AsyncPayloadAssembler.build_completed()`

### 4.2 Sync mode (`process`)
Muc tieu: khong stream, tra final ngay.

1. Parse input thanh `LogoGenerateInput`.
2. Kiem tra session da co guideline checkpoint chua.
3. Neu co guideline thi chay Stage C:
   - `OptionGenerationService.generate()`
   - `AsyncPayloadAssembler.build_completed()`
4. Neu khong co guideline thi fail voi `GUIDELINE_NOT_READY`.

## 5. Vai tro tung file trong source

### 5.1 Root modules
- `source/config.py`: doc env va tao config cho provider, timeout, redis, serpapi, gemini, asset path.
- `source/logger.py`: cau hinh root logger va helper `get_logger`.
- `source/__init__.py`: metadata package.

### 5.2 Context layer
- `source/context/session_store.py`: in-memory session store + CAS conflict (`ContextVersionConflictError`).
- `source/context/__init__.py`: export context symbols.

### 5.3 Schema layer
- `source/schemas/models.py`: toan bo Pydantic models (input, output, status, context, research, enums).
- `source/schemas/__init__.py`: re-export model symbols.

### 5.4 Services layer
- `source/services/stream_intake_handler.py`: orchestration Stage A/B, chunk timeline, clarification, checkpointing.
- `source/services/llm_logo_tools.py`: LLM-first tools (intent, extraction, topic swap, clarifications, guideline), fallback deterministic.
- `source/services/web_research_service.py`: query trend, fetch SerpAPI images, Gemini multimodal analysis, build research context.
- `source/services/context_merge_service.py`: merge precedence explicit > extracted > session.
- `source/services/required_field_gate.py`: danh gia required fields va tao suggested questions.
- `source/services/guideline_inference_service.py`: fallback infer guideline theo heuristic theo industry.
- `source/services/option_generation_service.py`: Stage C image generation + persist assets.
- `source/services/lifecycle_status_manager.py`: quan ly status/progress payload.
- `source/services/async_payload_assembler.py`: build payload completed/failed.
- `source/services/design_memory_service.py`: ghi versioned snapshot vao `design.md`.
- `source/services/provider_routing_policy.py`: chain provider/fallback policy (hien tai chu yeu o muc contract + test).
- `source/services/__init__.py`: barrel exports.

### 5.5 Task layer
- `source/tasks/logo_generate.py`: adapter voi AI Hub SDK, gom initialization va 2 execution mode (sync + stream).
- `source/tasks/__init__.py`: task discovery helper.

## 6. Nhung diem duplicate/logic cu can luu y

### 6.1 Duplicate keyword mapping industry
Dang co 2 ham mapping industry gan nhu trung nhau:
- `StreamIntakeHandler._extract_industry_from_text`
- `LogoDesignToolset._fallback_industry`

Rui ro:
- Lech behavior khi cap nhat tu khoa o mot ben ma quen ben kia.

De xuat:
- Trich ra helper chung (vi du `industry_heuristics.py`) va tai su dung.

### 6.2 Duplicate clarification template
Cau hoi mac dinh cho required fields dang ton tai o 2 noi:
- `required_field_gate.py` (`QUESTION_TEMPLATES`)
- `llm_logo_tools.py` (defaults trong `suggest_clarifications`)

Rui ro:
- Message clarification khong dong bo giua gate va toolset fallback.

De xuat:
- Dua vao 1 constant chung trong schema/service shared.

### 6.3 Stage C bi lap logic giua sync va stream
Trong `LogoGenerateTask`, doan goi `OptionGenerationService.generate()` + `build_completed()` xuat hien ca trong `process` va `stream_process`.

Danh gia:
- Khong phai bug, nhung la duplicate orchestration.

De xuat:
- Tao private helper cho Stage C (`_run_stage_c`) de gom logic.

### 6.4 Dau hieu code chua duoc dung trong runtime path
Mot so ham/class dang duoc test, nhung chua thay duoc goi trong runtime path chinh:
- `AsyncPayloadAssembler.build_failed`
- `WebResearchService.should_prioritize_research`
- Nhieu method trong `ProviderRoutingPolicy` (`select_primary`, `select_fallback`, `preserve_contract_payload_shape`) chua duoc su dung trong flow LLM hien tai
- `BrandContext.merge` (duoc test, flow chinh dung `ContextMergeService`)

Danh gia:
- Day la candidate cho dead/legacy code, chua can xoa ngay.
- Nen gan cờ TODO hoac bo sung integration usage neu du kien su dung.

## 7. Danh gia cach to chuc hien tai

### Diem tot
- Tach layer ro: schema/context/services/tasks.
- Orchestration tap trung tai `StreamIntakeHandler`, giup Stage A/B doc duoc theo timeline.
- `LogoGenerateTask` dung vai tro adapter dung nghia (SDK contract + delegate business logic).

### Diem can cai thien
- `services/` dang vua co orchestrator lon, vua co utility nho, va mot so module chua tham gia runtime path.
- Co duplicate heuristic va duplicate constants nhu muc 6.
- `source/api/` rong, de gay cam giac codebase chua trim gon.

## 8. De xuat refactor ngan gon (uu tien)
1. Tach `industry keyword mapping` thanh module dung chung.
2. Tach `clarification question templates` thanh 1 source of truth.
3. Gop Stage C sync/stream vao private helper trong `LogoGenerateTask`.
4. Danh dau ro modules test-only/legacy trong comment hoac ADR nho.
5. Neu chua dung `source/api/`, can nhac xoa folder rong de tranh nham lan.

## 9. Mot flow mau de hieu nhanh
- User stream request -> `LogoGenerateTask.stream_process`
- `StreamIntakeHandler.iter_chunks`:
  - intent/extract/merge/gate
  - neu thieu field -> clarification chunk + save checkpoint
  - neu du field -> web research + guideline + save checkpoint
- Quay lai `stream_process`:
  - generation started -> tao options -> completed payload
- Polling/sync request:
  - `LogoGenerateTask.process` doc checkpoint guideline
  - tao options + completed payload hoac tra loi `GUIDELINE_NOT_READY`

---
Tai lieu nay phu hop de on-board nhanh va audit architecture. Neu muon, co the tiep tuc bo sung sequence diagram (Mermaid) va bang dependency graph chi tiet theo symbol.
