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

# Dòng Chảy Toàn Bộ Quy Trình Logo Generation

**Từ Input → Stage A → Stage B → Stage C (với ví dụ cụ thể)**

---

## 📥 Input Ví Dụ

```json
{
  "session_id": "session_abc123",
  "query": "Logo công ty đồ uống thân thiện với môi trường",
  "brand_name": "EcoFlow",
  "industry": "Beverage/Sustainability",
  "style_preference": ["modern"],
  "color_preference": ["green"],
  "symbol_preference": ["leaf", "water drop"],
  "variation_count": 4,
  "use_session_context": true
}
```

---

## 🎯 STAGE A: Phát Hiện Ý Định → Hợp Nhất Context → Kiểm Tra Cổng

### Quy Trình Chi Tiết

```
Input Payload
    ↓
[LLM Gọi Phát Hiện Ý Định]
    ├─ Xác định: Tạo logo mới? Hay lặp lại logo hiện có?
    └─ Output: IntentDecision { action: "generate_new", confidence: 0.98 }
    
[Phân Tích Ảnh Tham Khảo (nếu có)]
    ├─ Trích xuất tín hiệu trực quan (phong cách, màu sắc, ký hiệu)
    └─ Output: ExtractionDecision { extracted_style: ["minimalist", "organic"], ... }
    
[Hợp Nhất Context]
    ├─ Nguồn 1: Context được cung cấp từ input
    ├─ Nguồn 2: Context trích xuất (từ ảnh tham khảo)
    ├─ Nguồn 3: Context phiên làm việc hiện có (nếu tái sử dụng session)
    └─ Quy Tắc Hợp Nhất: Explicit > Extracted > Session
    
Output: BrandContext {
  brand_name: "EcoFlow",
  industry: "Beverage",
  style_preference: ["modern", "minimalist", "organic"],
  color_preference: ["green"],
  symbol_preference: ["leaf", "water drop"],
  typography_direction: null  ← cần điền ở Stage B
}
    ↓
[Kiểm Tra Cổng - Các Trường Bắt Buộc]
    └─ brand_name ✓, industry ✓, missing: typography_direction
    
Output: GateResult {
  state: { brand_name: bắt_buộc✓, industry: bắt_buộc✓, typography_direction: thiếu },
  missing_fields: ["typography_direction"]
}
```

### Checkpoint Sau Stage A

```python
SessionContextState(
  session_id: "session_abc123",
  latest_brand_context: BrandContext(...),
  required_field_state: GateResult(...),
  latest_guidelines: [],  # ← chưa có, sẽ điền ở Stage B
  latest_research_context: None,
  context_version: 1
)
```

---

## 🔍 STAGE B: Nghiên Cứu Web → Phân Tích Từng Ảnh → Guideline Cho Mỗi Concept

### **Bước 1: Tạo Truy Vấn Tìm Kiếm**

```python
queries = [
  "xu hướng logo thiết kế 2026 đồ uống",
  "ví dụ danh tính thị giác thương hiệu đồ uống",
  "các thực hành tốt nhất thiết kế logo đồ uống",
]

# SerpAPI Search
results = await serp.search_async(queries)
  ├─ Truy vấn 1: 15 kết quả
  ├─ Truy vấn 2: 12 kết quả
  └─ Truy vấn 3: 18 kết quả
    → Loại bỏ URL/ảnh trùng lặp
    → Chọn 3 ảnh có thể lấy được
```

### **Bước 2: Phân Tích Multimodal Gemini (TỪNG ẢNH)**

```
Ảnh 0: "Logo Lá Xanh Hiện Đại"
├─ Prompt Gemini:
│   "Phân tích logo này cho:
│    - design_intelligence_market_analysis (xu hướng thị trường)
│    - strategic_design_direction (khái niệm chính)
│    - extracted_style_preference (phong cách trực quan)
│    - extracted_color_preference (màu sắc chiếm ưu thế)
│    - extracted_symbol_preference (yếu tố biểu tượng)
│    - extracted_typography_direction (hướng tiếp cận phông chữ)"
│
└─ Response (JSON):
   {
     "design_intelligence_market_analysis": [
       "Các thiết kế hình học tối giản đang, xu hướng năm 2024-2026",
       "Ký hiệu bền vững (lá, vòng tròn) chiếm ưu thế ở ngành đồ uống",
       "Kiểu chữ không chân được ưa thích cho các thương hiệu sinh thái hiện đại"
     ],
     "strategic_design_direction": "Khái Niệm Sinh Thái Tối Giản Hiện Đại",
     "extracted_style_preference": ["hình học", "đường sạch", "thiết kế phẳng"],
     "extracted_color_preference": ["xanh lá cây rừng", "không gian trắng"],
     "extracted_symbol_preference": ["lá được phong cách hóa", "hình dạng tròn"],
     "extracted_typography_direction": "kiểu chữ không chân hiện đại"
   }
    ↓
    PerImageAnalysis(
      image_index=0,
      image_url="https://...",
      market_analysis=[...],
      strategic_direction="Khái Niệm Sinh Thái Tối Giản Hiện Đại",
      extracted_style_preference=[...],
      extracted_color_preference=[...],
      extracted_symbol_preference=[...],
      extracted_typography_direction="kiểu chữ không chân hiện đại"
    )

Ảnh 1: "Logo Chai Nước Hình Dạng Có Đường Cong Hữu Cơ"
├─ Response: PerImageAnalysis(
     image_index=1,
     strategic_direction="Khái Niệm Sinh Thái Dòng Chảy Hữu Cơ",
     extracted_style_preference=["đường cong", "vẽ tay", "đường cong hữu cơ"],
     ...
   )

Ảnh 2: "Logo Thương Hiệu Bền Vững Hướng Đến Công Nghệ"
├─ Response: PerImageAnalysis(
     image_index=2,
     strategic_direction="Khái Niệm Bền Vững Hướng Đến Công Nghệ",
     extracted_style_preference=["tương lai hóa", "tối giản", "kỹ thuật số"],
     ...
   )

ResearchContext = {
  queries: [...],
  sources: [15 nguồn web],
  top_images: [Ảnh0, Ảnh1, Ảnh2],
  per_image_analyses: [
    PerImageAnalysis(0, "Khái Niệm Sinh Thái Tối Giản Hiện Đại", ...),
    PerImageAnalysis(1, "Khái Niệm Sinh Thái Dòng Chảy Hữu Cơ", ...),
    PerImageAnalysis(2, "Khái Niệm Bền Vững Hướng Đến Công Nghệ", ...)
  ],
  takeaways: [
    "Các thiết kế hình học tối giản đang xu hướng",
    "Ký hiệu bền vững rất quan trọng",
    "Kiểu chữ không chân được ưa thích",
    "Hình dạng dòng chảy hữu cơ đang nổi lên",
    ...
  ]
}
```

### **Bước 3: Suy Luận Guideline Cho Mỗi Concept (3 Lần Gọi LLM)**

```
Cho mỗi PerImageAnalysis → Tạo 1 DesignGuideline

Lần 1: infer_guideline_for_image_async(
  context: BrandContext("EcoFlow", "Beverage", style: ["modern"], color: ["green"]),
  per_image_analysis: PerImageAnalysis(0, "Khái Niệm Sinh Thái Tối Giản Hiện Đại", ...)
)
├─ Prompt Gemini:
│   "Dựa trên hướng chiến lược này và bối cảnh thương hiệu:
│    - Chiến lược: Khái Niệm Sinh Thái Tối Giản Hiện Đại
│    - Thông tin chi thị trường: Thiết kế tối giản đang xu hướng, bền vững rất quan trọng
│    - Tùy chọn trích xuất: hình học, đường sạch, xanh lá cây rừng
│    Tạo JSON guideline với: concept_statement, style_direction,
│    color_palette, typography_direction, icon_direction, constraints"
│
└─ Output: DesignGuideline {
     concept_statement: "Sinh thái tối giản hiện đại nhấn mạnh bền vững sạch sẽ",
     concept_variants: ["Khái Niệm Sinh Thái Tối Giản Hiện Đại"],
     style_direction: ["hình học", "đường sạch", "thiết kế phẳng", "trang trí tối thiểu"],
     color_palette: ["xanh lá cây rừng", "trắng", "xám nhạt", "nhấn đồng"],
     typography_direction: ["không chân", "hiện đại", "hình học"],
     icon_direction: ["ký hiệu lá tối giản", "vòng tròn hình học", "đường sạch"],
     constraints: ["không gradient", "tối đa 3 màu", "chỉ hình dạng hình học"]
   }

Lần 2: infer_guideline_for_image_async(
  context: BrandContext(...),
  per_image_analysis: PerImageAnalysis(1, "Khái Niệm Sinh Thái Dòng Chảy Hữu Cơ", ...)
)
└─ Output: DesignGuideline {
     concept_statement: "Danh tính trực quan tự nhiên-truyền cảm hứng dòng chảy hữu cơ",
     concept_variants: ["Khái Niệm Sinh Thái Dòng Chảy Hữu Cơ"],
     style_direction: ["đường cong hữu cơ", "vẽ tay", "dòng chảy", "hình dạng tự nhiên"],
     color_palette: ["xanh nhạt", "xám tự nhiên", "xanh nước", "tông màu đất"],
     typography_direction: ["không chân bo tròn", "thân thiện", "dòng chảy"],
     icon_direction: ["hình dạng nước dòng chảy", "hình dạng lá tự nhiên", "đường cong tự nhiên"],
     constraints: ["cho phép đường cong", "bảng màu đất, "cảm giác thủ công"]
   }

Lần 3: infer_guideline_for_image_async(
  context: BrandContext(...),
  per_image_analysis: PerImageAnalysis(2, "Khái Niệm Bền Vững Hướng Đến Công Nghệ", ...)
)
└─ Output: DesignGuideline {
     concept_statement: "Tính tối giản bền vững hướng đến công nghệ với độ chính xác hiện đại",
     concept_variants: ["Khái Niệm Bền Vững Hướng Đến Công Nghệ"],
     style_direction: ["tương lai hóa", "tối giản", "kỹ thuật số", "độ chính xác hình học"],
     color_palette: ["xanh lục", "than chì", "trắng", "nhấn kim loại"],
     typography_direction: ["không chân hiện đại", "hình học", "kỹ thuật"],
     icon_direction: ["lá lấy cảm hứng công nghệ", "lưới kỹ thuật số", "hình dạng độ chính xác"],
     constraints: ["cho phép góc cạnh", "th美học công nghệ", "độ chính xác bắt buộc"]
   }

latest_guidelines = [
  DesignGuideline(concept_statement="Sinh thái tối giản hiện đại..."),
  DesignGuideline(concept_statement="Dòng chảy hữu cơ..."),
  DesignGuideline(concept_statement="Hướng đến công nghệ...")
]
```

### Checkpoint Sau Stage B

```python
SessionContextState(
  session_id: "session_abc123",
  latest_brand_context: BrandContext({
    brand_name: "EcoFlow",
    industry: "Beverage",
    style_preference: ["modern", "geometric", "flowing", "futuristic"],  # được làm giàu
    color_preference: ["green", "forest green", "sage green", "teal"],   # được làm giàu
    symbol_preference: ["leaf", "water drop", "circle", "flowing forms"],# được làm giàu
    typography_direction: "sans-serif modern"  # được làm giàu ← điền trường thiếu!
  }),
  required_field_state: { brand_name: ✓, industry: ✓, typography_direction: ✓ },
  latest_guidelines: [
    DesignGuideline(concept_statement="Sinh thái tối giản hiện đại...", ...),
    DesignGuideline(concept_statement="Dòng chảy hữu cơ...", ...),
    DesignGuideline(concept_statement="Hướng đến công nghệ...", ...)
  ],
  latest_research_context: ResearchContext(...),
  context_version: 2
)
```

---

## 🎨 STAGE C: Tạo Logo Song Song (Cho Mỗi Concept)

```
Truy xuất session_state = SessionContextState(latest_guidelines=[3 guidelines])

Cho mỗi guideline trong latest_guidelines:
  
  Guideline 1: "Khái Niệm Sinh Thái Tối Giản Hiện Đại"
  ├─ Biến Thể Concept: ["Khái Niệm Sinh Thái Tối Giản Hiện Đại"]
  ├─ Phong Cách: ["hình học", "đường sạch"]
  ├─ Màu Sắc: ["xanh lá cây rừng", "trắng", "đồng"]
  ├─ Kiểu Chữ: ["không chân", "hiện đại"]
  │
  └─ Cho variation_count=4: Tạo 4 hình ảnh
      ├─ Tùy Chọn 1: prompt="Thiết kế logo sinh thái tối giản, lá hình học, xanh lá cây rừng, không chân"
      │   └─ Gọi Gemini + tạo thành s3://bucket/opt_1.png
      │       LogoOption(
      │         option_id="task_xyz_opt_1",
      │         concept_name="Khái Niệm Sinh Thái Tối Giản Hiện Đại",
      │         image_url="https://s3.../opt_1.png",
      │         seed=42,
      │         quality_flags=["gemini_generated"]
      │       )
      │
      ├─ Tùy Chọn 2: prompt="Thiết kế logo sinh thái tối giản, vòng tròn hình học, nền trắng, không chân"
      │   └─ LogoOption(option_id="task_xyz_opt_2", ...)
      │
      ├─ Tùy Chọn 3: prompt="Thiết kế logo sinh thái tối giản, nhấn đồng, thiết kế sạch"
      │   └─ LogoOption(option_id="task_xyz_opt_3", ...)
      │
      └─ Tùy Chọn 4: prompt="Thiết kế logo sinh thái tối giản, các yếu tố hình học khác nhau"
          └─ LogoOption(option_id="task_xyz_opt_4", ...)
  
  Guideline 2: "Khái Niệm Sinh Thái Dòng Chảy Hữu Cơ"
  ├─ Biến Thể Concept: ["Khái Niệm Sinh Thái Dòng Chảy Hữu Cơ"]
  ├─ Phong Cách: ["đường cong hữu cơ", "vẽ tay", "dòng chảy"]
  ├─ Màu Sắc: ["xanh nhạt", "xanh nước", "tông màu đất"]
  │
  └─ Cho variation_count=4: Tạo 4 hình ảnh
      ├─ Tùy Chọn 5: prompt="Thiết kế logo sinh thái dòng chảy hữu cơ, hình dạng nước, xanh nhạt"
      │   └─ LogoOption(option_id="task_xyz_opt_5", ...)
      ├─ Tùy Chọn 6: prompt="Thiết kế logo sinh thái dòng chảy hữu cơ, lá vẽ tay"
      │   └─ LogoOption(option_id="task_xyz_opt_6", ...)
      ├─ Tùy Chọn 7: ...LogoOption(option_id="task_xyz_opt_7", ...)
      └─ Tùy Chọn 8: ...LogoOption(option_id="task_xyz_opt_8", ...)
  
  Guideline 3: "Khái Niệm Bền Vững Hướng Đến Công Nghệ"
  ├─ Biến Thể Concept: ["Khái Niệm Bền Vững Hướng Đến Công Nghệ"]
  ├─ Phong Cách: ["tương lai hóa", "độ chính xác hình học"]
  ├─ Màu Sắc: ["xanh lục", "than chì", "kim loại"]
  │
  └─ Cho variation_count=4: Tạo 4 hình ảnh
      ├─ Tùy Chọn 9: prompt="Thiết kế logo công nghệ sinh thái, lá hình học, xanh lục"
      │   └─ LogoOption(option_id="task_xyz_opt_9", ...)
      ├─ Tùy Chọn 10: ...LogoOption(option_id="task_xyz_opt_10", ...)
      ├─ Tùy Chọn 11: ...LogoOption(option_id="task_xyz_opt_11", ...)
      └─ Tùy Chọn 12: ...LogoOption(option_id="task_xyz_opt_12", ...)

Tổng Tạo: 12 tùy chọn (3 concepts × 4 biến thể)
  sắp xếp theo: (seed, option_id)
```

### Output Cuối Cùng

```python
LogoGenerateOutput(
  guideline: DesignGuideline(  # sử dụng guideline đầu tiên cho output cuối cùng
    concept_statement="Sinh thái tối giản hiện đại...",
    concept_variants=["Khái Niệm Sinh Thái Tối Giản Hiện Đại"],
    ...
  ),
  required_field_state: { brand_name: ✓, industry: ✓, typography: ✓ },
  options: [
    LogoOption(option_id="task_xyz_opt_1", concept_name="Khái Niệm Sinh Thái Tối Giản Hiện Đại", image_url="s3://...png", ...),
    LogoOption(option_id="task_xyz_opt_2", concept_name="Khái Niệm Sinh Thái Tối Giản Hiện Đại", image_url="s3://...png", ...),
    LogoOption(option_id="task_xyz_opt_3", concept_name="Khái Niệm Sinh Thái Tối Giản Hiện Đại", image_url="s3://...png", ...),
    LogoOption(option_id="task_xyz_opt_4", concept_name="Khái Niệm Sinh Thái Tối Giản Hiện Đại", image_url="s3://...png", ...),
    LogoOption(option_id="task_xyz_opt_5", concept_name="Khái Niệm Sinh Thái Dòng Chảy Hữu Cơ", image_url="s3://...png", ...),
    LogoOption(option_id="task_xyz_opt_6", concept_name="Khái Niệm Sinh Thái Dòng Chảy Hữu Cơ", image_url="s3://...png", ...),
    ...
    LogoOption(option_id="task_xyz_opt_12", concept_name="Khái Niệm Bền Vững Hướng Đến Công Nghệ", image_url="s3://...png", ...),
  ]
)
```

---

## 📈 Sơ Đồ Dòng Chảy Dữ Liệu Context

```
┌─────────────────────────────────────────────────────────────────┐
│                 STAGE A: Kiểm Tra & Hợp Nhất                   │
├─────────────────────────────────────────────────────────────────┤
│ INPUT                                                            │
│ ├─ query: "Logo công ty đồ uống thân thiện với môi trường"      │
│ ├─ brand_name: "EcoFlow"                                        │
│ ├─ style_preference: ["modern"]                                 │
│ └─ color_preference: ["green"]                                  │
│                                                                  │
│ XỬ LÝ                                                            │
│ ├─ Ý Định → "generate_new"                                      │
│ ├─ Phân Tích Ảnh Tham Khảo → trích xuất tín hiệu                │
│ └─ Hợp Nhất: explicit > extracted > session                     │
│                                                                  │
│ OUTPUT: BrandContext                                            │
│ ├─ brand_name: "EcoFlow" ✓                                      │
│ ├─ industry: "Beverage" ✓                                       │
│ ├─ style_preference: ["modern", "minimalist", "organic"]        │
│ ├─ color_preference: ["green"]                                  │
│ └─ typography_direction: null ← THIẾU                           │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│              STAGE B: Nghiên Cứu & Guideline                    │
├─────────────────────────────────────────────────────────────────┤
│ NGHIÊN CỨU                                                       │
│ ├─ Truy Vấn: 3 truy vấn tìm kiếm qua SerpAPI                    │
│ ├─ Kết Quả: ~45 nguồn, 100+ ảnh                                 │
│ └─ Chọn: 3 ảnh có thể lấy được hàng đầu                         │
│                                                                  │
│ PHÂN TÍCH GEMINI (3 lần - từng ảnh)                             │
│ ├─ Ảnh 0 → PerImageAnalysis(                                    │
│ │              index=0,                                          │
│ │              strategic_direction="Tối Giản Hiện Đại",        │
│ │              market_analysis=[...],                           │
│ │              extracted_style_preference=["hình học"],         │
│ │              ...                                               │
│ │            )                                                   │
│ ├─ Ảnh 1 → PerImageAnalysis(index=1, "Dòng Chảy Hữu Cơ", ...)   │
│ └─ Ảnh 2 → PerImageAnalysis(index=2, "Hướng Đến Công Nghệ", ...)│
│                                                                  │
│ DUYỆT GUIDELINE (3 lần - mỗi concept)                           │
│ ├─ Concept 0: DesignGuideline {                                 │
│ │   concept_statement: "Sinh thái tối giản hiện đại",          │
│ │   style_direction: ["hình học", "đường sạch"],               │
│ │   color_palette: ["xanh lá cây rừng", "trắng"],              │
│ │   typography_direction: ["không chân"],                       │
│ │   ...                                                          │
│ │ }                                                              │
│ ├─ Concept 1: DesignGuideline { "Dòng chảy hữu cơ", ... }      │
│ └─ Concept 2: DesignGuideline { "Hướng đến công nghệ", ... }   │
│                                                                  │
│ OUTPUT: ResearchContext + BrandContext (được làm giàu)          │
│ ├─ per_image_analyses: [3 PerImageAnalysis]                     │
│ ├─ brand_context được làm giàu: typography_direction="sans"✓    │
│ └─ latest_guidelines: [3 DesignGuideline]                       │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│                  STAGE C: Tạo & Output                          │
├─────────────────────────────────────────────────────────────────┤
│ TẠO SONG SONG (3 concepts × 4 biến thể = 12 tùy chọn)          │
│                                                                  │
│ Concept 0: Tối Giản Hiện Đại                                    │
│ ├─ DesignGuideline { color_palette: ["xanh rừng"] }             │
│ └─ Tùy Chọn: 4 biến thể                                         │
│     ├─ opt_1: prompt="logo hình học tối giản, xanh"            │
│     ├─ opt_2: prompt="ký hiệu lá tối giản, sạch"               │
│     ├─ opt_3: prompt="hình dạng vòng tròn tối giản, nền trắng" │
│     └─ opt_4: prompt="tối giản đồng + nhấn xanh"               │
│                                                                  │
│ Concept 1: Dòng Chảy Hữu Cơ                                     │
│ ├─ DesignGuideline { color_palette: ["xanh nhạt", "nước"] }     │
│ └─ Tùy Chọn: 4 biến thể                                         │
│     ├─ opt_5: prompt="hình dạng nước dòng chảy, xanh nhạt"     │
│     ├─ opt_6: prompt="lá vẽ tay đường cong, hữu cơ"            │
│     ├─ opt_7: prompt="nước dòng chảy + kết hợp lá"             │
│     └─ opt_8: prompt="hình dạng hữu cơ, tông màu đất"          │
│                                                                  │
│ Concept 2: Hướng Đến Công Nghệ                                  │
│ ├─ DesignGuideline { color_palette: ["xanh lục", "than chì"] }  │
│ └─ Tùy Chọn: 4 biến thể                                         │
│     ├─ opt_9: prompt="logo lá công nghệ, xanh lục"             │
│     ├─ opt_10: prompt="hình dạng độ chính xác, than + xanh"    │
│     ├─ opt_11: prompt="lưới kỹ thuật số + ký hiệu lá"          │
│     └─ opt_12: prompt="nhấn kim loại hình học"                 │
│                                                                  │
│ OUTPUT: LogoGenerateOutput                                      │
│ ├─ guideline: DesignGuideline đầu tiên (Tối Giản)              │
│ ├─ required_field_state: tất cả trường ✓                        │
│ └─ options: [12 LogoOption với URLs]                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔑 Các Hiểu Biết Chính

✅ **Phân Tích Từng Ảnh** → Mỗi ảnh được phân tích độc lập (xu hướng thị trường, hướng chiến lược)  
✅ **Cô Lập Concept** → 3 guideline khác nhau, không chia sẻ tùy chọn  
✅ **Căn Chỉnh Ngữ Nghĩa** → Mỗi concept mang lại color/style từ ảnh nguồn của nó  
✅ **Output Phong Phú** → 12 tùy chọn so với 3-4 trước (gấp 3x thêm variety)  
✅ **Làm Giàu Context** → Các trường thiếu được điền từ thông tin nghiên cứu  

---

## 📚 Tham Chiếu Kỹ Thuật

- **Stage A**: `source/workers/stage_a_worker.py`, `source/services/stage_a/toolset.py`
- **Stage B**: `source/workers/stage_b_worker.py`, `source/services/stage_b/`
- **Stage C**: `source/workers/stage_c_worker.py`, `source/services/stage_c/`
- **Schemas**: `source/schemas/domain.py` (BrandContext, PerImageAnalysis, DesignGuideline)
- **Context**: `source/context/session_context_store.py`, `source/schemas/status.py` (SessionContextState)

