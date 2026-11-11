# YouTube Script AI Specification

## Purpose
Hệ thống hỗ trợ nhà sáng tạo nội dung tạo kịch bản YouTube song ngữ (Anh - Việt) từ video nước ngoài bằng cách trích xuất transcript, phân tích cấu trúc bằng Gemini API, và sinh kịch bản tương ứng.
## Requirements
### Requirement: Cấu hình Gemini API Key
Hệ thống MUST cho phép người dùng nhập và lưu trữ Gemini API Key dưới LocalStorage của trình duyệt. API Key MUST NOT được lưu trữ trên backend server mà chỉ gửi kèm qua request header `X-Gemini-API-Key`.

#### Scenario: Khách hàng cấu hình API Key thành công
- **WHEN** Người dùng nhập API Key vào ô cấu hình và nhấn lưu
- **THEN** Hệ thống lưu key vào localStorage của trình duyệt
- **AND** Các request tiếp theo gửi lên backend sẽ đính kèm header `X-Gemini-API-Key`

---

### Requirement: Nhập và Validate URL YouTube
Hệ thống MUST tiếp nhận đường dẫn video YouTube từ người dùng và kiểm tra tính hợp lệ trước khi xử lý tiếp.

#### Scenario: Validate đường dẫn YouTube hợp lệ
- **WHEN** Người dùng nhập URL dạng `https://www.youtube.com/watch?v=...` hoặc `https://youtu.be/...`
- **THEN** Hệ thống xác định URL hợp lệ và trích xuất `video_id`

#### Scenario: Nhập đường dẫn không hợp lệ
- **WHEN** Người dùng nhập chuỗi không đúng định dạng video YouTube
- **THEN** Hệ thống hiển thị lỗi cảnh báo định dạng không hợp lệ

---

### Requirement: Lấy Transcript tự động và Thủ công
Hệ thống MUST cố gắng lấy phụ đề (transcript) tự động thông qua API của backend. Nếu video không có phụ đề hoặc bị chặn, hệ thống MUST hiển thị khung nhập thủ công để người dùng dán transcript.

#### Scenario: Lấy phụ đề tự động thành công
- **WHEN** Backend gọi thư viện lấy phụ đề cho `video_id` thành công
- **THEN** Trả về toàn bộ text transcript kèm theo mốc thời gian (nếu có)
- **AND** Hiển thị trên giao diện trạng thái đã lấy xong phụ đề

#### Scenario: Fallback sang nhập transcript thủ công
- **WHEN** Backend báo lỗi không tìm thấy phụ đề (video không có sub, bị chặn quốc gia,...)
- **THEN** Hệ thống hiển thị textarea yêu cầu người dùng copy và dán transcript thủ công

---

### Requirement: Phân tích cấu trúc kịch bản và sinh song ngữ
Hệ thống MUST gửi transcript và prompt định dạng chuẩn tới Gemini API để phân tích cấu trúc (Outline) gồm các phần (Hook, Act 1, Act 2, Conclusion, Tone, Duration), sau đó sinh kịch bản song ngữ Anh - Việt tương ứng. Dữ liệu phản hồi MUST tuân thủ định dạng JSON nghiêm ngặt để đảm bảo phân tách chính xác giữa cấu trúc, kịch bản gốc tiếng Anh và bản Việt hóa. Đồng thời, hệ thống MUST xử lý lỗi kết nối và giới hạn tần suất gọi (rate limiting) của Gemini API và phản hồi thông tin lỗi rõ ràng cho phía Client hiển thị.

#### Scenario: Phân tích và sinh kịch bản thành công
- **WHEN** Backend nhận được transcript hợp lệ (hoặc dán thủ công) và gọi Gemini API với prompt tối ưu cấu trúc
- **THEN** Gemini trả về cấu trúc JSON hợp lệ chứa outline chi tiết, kịch bản tiếng Anh và kịch bản tiếng Việt
- **AND** Hệ thống lưu trữ/trả về kết quả cho phía Client hiển thị dạng song ngữ
- **AND** Gợi ý kịch bản trả về chứa thông tin `narrative_shape` hỗ trợ dựng cấu trúc cảm xúc

#### Scenario: Lỗi sinh kịch bản do quá giới hạn tần suất gọi (Rate Limit)
- **WHEN** Backend gọi Gemini API nhưng nhận phản hồi lỗi 429 hoặc quá tải và đã retry thất bại
- **THEN** Backend trả về thông tin lỗi chi tiết về rate limit
- **AND** Frontend hiển thị thông báo lỗi thân thiện gợi ý người dùng kiểm tra lại API key hoặc thử lại sau

### Requirement: Môi trường triển khai thực tế (Production Deployment)
Hệ thống MUST được cấu hình để triển khai dễ dàng lên các môi trường production:
- Backend MUST hỗ trợ chạy bằng Docker (Dockerfile) và cho phép cấu hình CORS, Port qua biến môi trường.
- Frontend MUST cấu hình định tuyến (vercel.json) để chạy trên Vercel không bị lỗi 404 khi reload, và tự động sử dụng URL API backend từ biến môi trường `VITE_API_URL` (nếu có) hoặc fallback về local url.

#### Scenario: Cấu hình deploy Backend thành công với Docker
- **WHEN** Chạy container từ Dockerfile của backend
- **THEN** Backend khởi chạy dịch vụ FastAPI thành công trên cổng được chỉ định, chấp nhận kết nối CORS từ domain frontend cấu hình qua biến môi trường.

#### Scenario: Cấu hình deploy Frontend thành công trên Vercel
- **WHEN** Deploy frontend lên Vercel và truy cập ứng dụng
- **THEN** Trang web tải thành công, các route tĩnh hoạt động bình thường, và gọi API backend dựa trên biến môi trường `VITE_API_URL`.

---

### Requirement: Tối ưu hóa và Polish UX
Giao diện người dùng MUST được tinh chỉnh hoàn thiện (Polish UX/UI):
- Hỗ trợ responsive đầy đủ trên mọi kích thước màn hình (mobile, tablet, desktop). Trên màn hình nhỏ, thay vì chia 2 cột song song sẽ hiển thị dạng tab toggle để đảm bảo nội dung dễ đọc.
- Bố cục vùng hiển thị kịch bản và outline MUST có thanh cuộn riêng biệt (inner scroll) để tránh làm cuộn toàn bộ trang web khi đọc kịch bản dài.
- Hiển thị trạng thái sao chép (copy) rõ ràng cho từng phân đoạn kịch bản và cho toàn bộ kịch bản.

#### Scenario: Chuyển đổi hiển thị linh hoạt trên thiết bị di động
- **WHEN** Chiều rộng màn hình thiết bị nhỏ hơn 768px (Mobile/Tablet)
- **THEN** Giao diện tự động chuyển đổi từ hiển thị song ngữ 2 cột sang hiển thị dạng Tab (tab English | tab Tiếng Việt) để tối ưu không gian hiển thị.

#### Scenario: Sao chép phân đoạn kịch bản riêng biệt
- **WHEN** Người dùng nhấn nút "Copy" tại một phân đoạn cụ thể trong kịch bản song ngữ
- **THEN** Hệ thống chỉ sao chép nội dung phân đoạn đó và hiển thị trạng thái "Đã copy!" riêng biệt tại phân đoạn đó trong 2 giây.

### Requirement: Toàn cục tuần tự Fact-Check và xác thực Verifiability Level
Hệ thống MUST kiểm định dữ liệu lịch sử/khoa học toàn cục trên toàn bộ các phân cảnh trong một lượt chạy duy nhất để phát hiện lỗi mâu thuẫn mốc thời gian (timeline conflict) hoặc lặp nội dung (redundancy). Mỗi phân cảnh MUST được đánh dấu thuộc tính `verifiability_level` (`specific_event`, `general_consensus`, `unverifiable_generalization`). Nếu cảnh có mốc `unverifiable_generalization` trong kịch bản lịch sử, hệ thống MUST bắt buộc viết lại phân cảnh đó.

#### Scenario: Kiểm duyệt lịch sử thành công và trả về danh sách scene sửa đổi
- **WHEN** Phase 8 Fact-Check được kích hoạt
- **THEN** Hệ thống MUST gửi toàn bộ danh sách phân cảnh hiện tại tới Gemini API để kiểm định toàn cục
- **AND** Gemini API chỉ trả về danh sách các phân cảnh bị phát hiện có lỗi cần sửa đổi cùng với thuộc tính `verifiability_level` thích hợp
- **AND** Hệ thống tự động merge các phân cảnh sửa đổi này vào kịch bản gốc

### Requirement: Longform stage-scoped scene generation
The system MUST keep longform scene generation aligned with the scene ranges declared by the approved blueprint/story spine. Each scene batch MUST receive only the stage context that overlaps its requested scene numbers, while preserving the public API, SSE event keys, and canonical v3 output shape.

#### Scenario: Batch receives only matching historical chapter
- **WHEN** a 60-scene historical script has stages `1-20`, `21-40`, and `41-60`
- **THEN** the scene-generation prompt for scenes `1-10` includes only the stage overlapping scenes `1-10`
- **AND** it does not include later Napoleon or Hitler stage text

#### Scenario: Routed narrative shape is persisted
- **WHEN** the backend resolves a routing rule for a historical or scientific production run
- **THEN** the live work-state and canonical v3 save include the resolved `narrative_shape`
- **AND** the canonical topic metadata does not store `narrative_shape` as `null` when a routing default exists

### Requirement: Emotion arc generation remains bounded
The system MUST avoid strict emotion-arc retry loops for stage/person mismatch rules that are better validated after concrete scene candidates exist. Emotion arc generation MAY record advisory warnings for chapter drift, but it MUST NOT add additional LLM retries for those warnings.

#### Scenario: Arc mismatch warning does not trigger extra retry
- **WHEN** an emotion arc chunk contains a lead character that appears outside the expected stage range
- **THEN** the system records a warning for observability
- **AND** it does not retry the arc chunk solely because of that warning

#### Scenario: Scene candidate mismatch blocks later
- **WHEN** a generated scene candidate places a named historical figure in a stage range assigned to a different named figure
- **THEN** Phase 2 candidate validation rejects the scene candidate before it is accepted into final output

### Requirement: Production LLM calls are observable and bounded
The system MUST bound long-running production LLM calls with phase-level timeout handling and record latency context. Timeout failures MUST surface through the existing production error flow rather than leaving the stream apparently stalled.

#### Scenario: Slow provider call times out cleanly
- **WHEN** a production LLM call exceeds the configured timeout for its phase or chunk
- **THEN** the phase fails with a structured error through the existing stream safety path
- **AND** phase logs include enough context to identify the phase and scene range involved

### Requirement: Strict fact-check completion reflects scene-level verification
For historical and scientific production runs, the system MUST keep fact-check prompts scoped to the current chunk and MUST reject malformed, unknown, or invalid patches without merging them into the screenplay. Sparse successful patches remain allowed for unchanged accurate scenes, and completed Phase 4 runs MUST expose per-scene verification status.

#### Scenario: Unknown fact-check scene patch is rejected
- **WHEN** a fact-check chunk for scenes `1-12` returns a patch for scene `31`
- **THEN** the system rejects that patch and records a quality warning
- **AND** it does not merge the patch into any scene
- **AND** the production run does not fail solely because of the off-range patch

#### Scenario: Invalid correction patch becomes review status
- **WHEN** a fact-check correction patch still violates measurable scene gates after retry
- **THEN** the system preserves the original scene content
- **AND** marks the affected scene as `needs_review`
- **AND** final code validation still hard-fails if the resulting screenplay has schema, anchor, voice, or coverage errors
