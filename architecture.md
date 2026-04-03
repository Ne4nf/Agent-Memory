# Review Mã Nguồn

## Phạm vi

Bản review này chỉ xét package `source` và giải thích toàn bộ luồng tạo logo end-to-end: AI Hub SDK entrypoint, các stage service, schema, session memory, và UI Streamlit.

## Kết luận tóm tắt

Ở mức kiến trúc, code khá sạch: luồng được tách rõ, dùng schema làm hợp đồng dữ liệu, và đa số nhánh quan trọng đều fail-closed. Tôi không thấy path nào bịa research, bịa guideline, hay bịa ảnh logo để “lấp chỗ trống” cho user.

Tuy nhiên code chưa thể gọi là “không còn fallback” hoàn toàn. Hiện vẫn có một số heuristic/fallback có chủ đích:

- câu hỏi clarification có fallback sang bộ câu hỏi mặc định nếu LLM trả không hợp lệ,
- session context được reuse cho follow-up trong cùng `session_id`,
- UI có fallback đọc ảnh local/remote để ổn định render,
- một số nhánh compatibility cũ vẫn còn để giữ test/support ổn định.

Nói ngắn gọn: code không “bịa data”, nhưng vẫn còn một vài fallback có chủ đích để hệ thống không bị kẹt.

## Luồng Full Flow

### 1. Điểm vào task

File: [source/tasks/logo_generate.py](../../source/tasks/logo_generate.py)

`LogoGenerateTask` là adapter của AI Hub SDK, kế thừa `BaseTask`. File này không chứa nghiệp vụ nặng mà chỉ làm nhiệm vụ cầu nối giữa framework và service business.

Các việc chính:

- khai báo `task_type = "logo_generate"`,
- bind input schema `LogoGenerateInput`,
- bind output stream schema `LogoGenerateTaskOutput`,
- khởi tạo singleton service cho worker một lần,
- điều phối stream qua Stage A/B rồi sang Stage C.

Hàm quan trọng nhất là `stream_process()`:

1. chuyển `input_args` thành dict,
2. gọi `StreamIntakeHandler.iter_chunks()` cho Stage A/B,
3. nếu Stage A/B chưa completed thì dừng luôn,
4. nếu Stage A/B completed thì gọi `StreamGenerationOrchestrator.iter_chunks()` cho Stage C,
5. wrap từng chunk về `LogoGenerateTaskOutput`.

### 2. Schema layer

File: [source/schemas/__init__.py](../../source/schemas/__init__.py)

Đây là lớp contract trung tâm. File này chỉ re-export model từ `api.py`, `domain.py`, `status.py`, `enums.py` để các service import một chỗ.

Các model chính:

- `LogoGenerateInput`: input cho task,
- `BrandContext`: context thương hiệu đã merge,
- `RequiredFieldState`: trạng thái đủ/thiếu field bắt buộc,
- `ResearchContext`: kết quả web research,
- `DesignGuideline`: guideline thiết kế,
- `LogoOption`: metadata logo output,
- `SessionContextState`: snapshot session,
- `JobStatusResponse`: payload trạng thái stream/async.

Ý nghĩa thực tế: thay vì truyền dict rời rạc giữa các stage, code dùng model typed để giảm lỗi shape và giúp pipeline rõ ràng hơn.

### 3. Config layer

File: [source/config.py](../../source/config.py)

File này gom toàn bộ biến môi trường/runtime config cho hệ thống.

Nó định nghĩa:

- cấu hình AI Hub SDK (`AI_HUB_SDK_*`),
- Gemini text/image model,
- SerpAPI key/endpoint/limit,
- storage path và asset URL,
- timeout, retry, cost trace,
- mode provider ảnh (`IMAGE_PROVIDER_MODE`),
- số lượng ảnh top cần xử lý trong research.

Điểm cần lưu ý:

- `IMAGE_PROVIDER_MODE` mặc định là `mock`, nhưng Stage C hiện không sinh mock image giả để che lỗi. Nếu provider không bật thì nó fail closed.

## Stage A

### Các file liên quan

- [source/services/stage_a/handler.py](../../source/services/stage_a/handler.py)
- [source/services/stage_a/orchestrator.py](../../source/services/stage_a/orchestrator.py)
- [source/services/stage_a/toolset.py](../../source/services/stage_a/toolset.py)
- [source/services/stage_a/llm_runtime.py](../../source/services/stage_a/llm_runtime.py)
- [source/services/stage_a/checkpoint.py](../../source/services/stage_a/checkpoint.py)

### Stage A làm gì

Stage A là cửa vào cho intake và clarification.

Nó quyết định 3 việc:

1. có đúng là user đang yêu cầu logo không,
2. có trích xuất được brand context từ query/reference không,
3. có đủ `brand_name` và `industry` để qua Stage B không.

### Luồng xử lý

`StreamIntakeHandler` chỉ là adapter mỏng để giữ API cũ, còn logic thật nằm ở `StreamIntakeOrchestrator`.

`StreamIntakeOrchestrator.iter_chunks()` làm theo thứ tự:

1. load snapshot session cũ,
2. emit chunk intake,
3. gọi `LogoDesignToolset.detect_intent_async()`,
4. gọi `extract_inputs_async()` và `analyze_reference_images_async()`,
5. merge explicit input + extracted data + session fallback,
6. đánh giá `RequiredFieldState`,
7. nếu thiếu field bắt buộc thì emit clarification và dừng,
8. nếu đủ thì handoff sang Stage B.

### AI Hub SDK được dùng như thế nào

Stage A không gọi SDK “thô” trực tiếp ở nhiều nơi; nó đi qua task adapter và lifecycle manager:

- `BaseTask` cho contract task,
- `TaskOutputBaseModel` cho stream output,
- `ServingMode.STREAM` để chạy dạng stream,
- `build_status_response()` để chuẩn hóa chunk payload.

### Đánh giá heuristic/fallback ở Stage A

Có một fallback cố ý:

- `suggest_clarifications_async()` ưu tiên lấy câu hỏi từ LLM,
- nếu LLM fail thì rơi xuống bộ câu hỏi mặc định hardcoded.

Đây không phải bịa dữ liệu sản phẩm. Nó chỉ là UX fallback để tránh user bị kẹt khi model không trả về câu hỏi hợp lệ.

Cũng có heuristic reuse session:

- follow-up trong cùng `session_id` sẽ lấy context cũ làm fallback,
- nhưng nó được giới hạn rõ bằng `context_version` và rule merge.

### Chỗ còn nên để ý

Trong Stage A toolset, một số prompt text rất cứng tay, ví dụ yêu cầu LLM chỉ trả field explicit, không được đoán. Đây là tốt về mặt an toàn, nhưng vẫn là heuristic prompt-based chứ không phải rule engine thuần.

## Stage B

### Các file liên quan

- [source/services/stage_b/web_research_service.py](../../source/services/stage_b/web_research_service.py)
- [source/services/stage_b/research_clients.py](../../source/services/stage_b/research_clients.py)
- [source/services/stage_b/research_normalizer.py](../../source/services/stage_b/research_normalizer.py)
- [source/services/stage_b/gemini_analyzer.py](../../source/services/stage_b/gemini_analyzer.py)
- [source/services/stage_b/orchestrator.py](../../source/services/stage_b/orchestrator.py)

### Stage B làm gì

Stage B là phần enrich guideline bằng web research theo domain logo.

Luồng hiện tại:

1. build 3 query từ `industry`,
2. gọi SerpAPI song song cho 3 query,
3. dedupe source/image,
4. chọn top images,
5. gọi Gemini phân tích top ảnh,
6. aggregate strategic directions và signals,
7. infer `DesignGuideline`,
8. checkpoint lại kết quả.

### AI Hub SDK usage

Stage B vẫn đi theo cùng contract stream status với Stage A. Tức là nó build chunk status thông qua lifecycle manager rồi task adapter pass qua UI.

### Latency thật sự đến từ đâu

Stage B đã parallel nhưng vẫn có 2 pha nối tiếp:

- pha 1: SerpAPI song song cho 3 query,
- pha 2: Gemini song song cho top 3 ảnh,
- sau đó mới merge, infer guideline và checkpoint.

Nghĩa là latency Stage B vẫn cao vì đây là pipeline network-heavy có 2 tầng gọi ngoài mạng nối tiếp nhau, không phải vì chỉ có 1 call blocking đơn lẻ.

### Đánh giá heuristic/fallback ở Stage B

Ở đây không thấy bịa research hay bịa guideline.

Các điểm fail-closed khá rõ:

- `SerpApiImageClient` fail nếu API thiếu hoặc request lỗi,
- `GeminiResearchAnalyzer` fail nếu response multimodal rỗng/không hợp lệ,
- `StageBPipeline` chỉ persist sau khi guideline thật đã tạo xong.

Tuy nhiên, phần `GeminiResearchAnalyzer` vẫn còn một số helper legacy như:

- `_generate_payload_text_only()`
- `_generate_payload_text_only_async()`
- `_filter_fetchable_images()`
- `_filter_fetchable_images_async()`

Hiện luồng chính đã đi theo per-image parallel analysis, nên các helper này chủ yếu là compatibility/legacy. Chúng không phải main path, nhưng nếu muốn code “sạch tuyệt đối” thì nên dọn tiếp.

### Kết luận riêng cho Stage B

- Không thấy bịa data.
- Có heuristic prompt.
- Có legacy fallback code còn sót.
- Đây là phần cần dọn tiếp nếu bạn muốn codebase strict hơn nữa.

## Stage C

### Các file liên quan

- [source/services/stage_c/orchestrator.py](../../source/services/stage_c/orchestrator.py)
- [source/services/stage_c/generator.py](../../source/services/stage_c/generator.py)

### Stage C làm gì

Stage C sinh logo options thật.

Luồng:

1. load guideline đã checkpoint,
2. fail nếu chưa có guideline,
3. emit generation-start chunk,
4. generate 3-4 option song song,
5. upload asset và lấy public URL,
6. emit chunk completed cuối cùng.

### Đánh giá heuristic/fallback ở Stage C

Stage C cũng fail closed:

- nếu provider không sẵn sàng thì raise `GEMINI_UNAVAILABLE`,
- không sinh ảnh giả,
- không bịa logo placeholder để lấp trạng thái.

Chỗ duy nhất mang tính heuristic là prompt directive:

- ép brand text phải đúng,
- giảm gibberish lettering,
- ràng buộc style/colors/constraints để kết quả ổn định hơn.

Đây là heuristic cho generation, không phải fallback dữ liệu.

## UI layer

### File

- [streamlit_logo_flow_demo.py](../../streamlit_logo_flow_demo.py)

### UI làm gì

UI là demo Streamlit, không phải source of truth của backend.

Nó làm các việc:

- dựng giao diện chat,
- submit input,
- stream reasoning chunk,
- render reference images,
- render canvas,
- giữ chat history trong `st.session_state`.

### Đánh giá fallback ở UI

UI có fallback render hợp lý:

- nếu upload file thì render bytes trực tiếp,
- nếu là local file path thì resolve path,
- nếu là remote URL thì thử download,
- nếu download fail thì để browser thử load URL.

Đây là resilience cho UI, không phải bịa data.

## Đánh giá theo file

### Sạch và chấp nhận được

- [source/tasks/logo_generate.py](../../source/tasks/logo_generate.py)
- [source/context/session_store.py](../../source/context/session_store.py)
- [source/services/shared/lifecycle_status.py](../../source/services/shared/lifecycle_status.py)
- [source/services/shared/payload_assembler.py](../../source/services/shared/payload_assembler.py)
- [source/services/stage_a/checkpoint.py](../../source/services/stage_a/checkpoint.py)
- [source/services/stage_b/web_research_service.py](../../source/services/stage_b/web_research_service.py)
- [source/services/stage_b/research_clients.py](../../source/services/stage_b/research_clients.py)
- [source/services/stage_c/orchestrator.py](../../source/services/stage_c/orchestrator.py)
- [source/services/stage_c/generator.py](../../source/services/stage_c/generator.py)

### Sạch nhưng có fallback có chủ đích

- [source/services/stage_a/toolset.py](../../source/services/stage_a/toolset.py): clarification fallback mặc định nếu LLM fail,
- [source/services/stage_a/orchestrator.py](../../source/services/stage_a/orchestrator.py): reuse session context cho follow-up,
- [streamlit_logo_flow_demo.py](../../streamlit_logo_flow_demo.py): fallback render ảnh local/remote,
- [source/tasks/logo_generate.py](../../source/tasks/logo_generate.py): fallback import cho compatibility test cũ,
- [source/config.py](../../source/config.py): default `mock` ở config, nhưng không có mock image fabrication path.

### Cần dọn tiếp nếu muốn strict hơn

- [source/services/stage_b/gemini_analyzer.py](../../source/services/stage_b/gemini_analyzer.py): còn helper legacy text-only/fetchability,
- [source/services/stage_b/gemini_analyzer.py](../../source/services/stage_b/gemini_analyzer.py): prompt và branch compatibility chưa được tối giản hết.

## Review sâu hơn: có heuristic/fallback bịa data không?

### Không thấy bịa data ở các đường chính

Tôi không thấy path nào đang:

- tự dựng research result giả,
- tự dựng guideline giả,
- tự dựng logo image output giả,
- hoặc giả completed status khi pipeline chưa xong.

### Các fallback còn lại là gì

1. Fallback clarification questions trong Stage A.
2. Reuse session context trong cùng `session_id`.
3. Fallback image preview trong UI.
4. Legacy helper path trong Stage B analyzer.

### Đánh giá rủi ro còn lại

- Rủi ro kỹ thuật lớn nhất hiện tại là latency Stage B.
- Rủi ro maintainability lớn nhất là `gemini_analyzer.py` còn code cũ chưa dọn.
- Rủi ro “bịa data” thấp, vì các stage chính đều fail closed.

## Kết luận cuối

Nếu hỏi thẳng: `source` đã clean chưa?

- Về luồng nghiệp vụ và data integrity: khá clean.
- Về heuristic/fallback bịa data: không thấy bịa data ở đường chính.
- Về code hygiene tuyệt đối: chưa sạch hoàn toàn, vì `source/services/stage_b/gemini_analyzer.py` còn legacy fallback/helper cần dọn tiếp.

Nếu bạn muốn làm strict hơn nữa, bước kế tiếp hợp lý nhất là tối giản `gemini_analyzer.py` về một luồng duy nhất và bỏ các helper text-only / fetchability cũ không còn dùng trên main path.
