## Why

Dự án YouTube Script AI Generator cần bước khởi tạo nền tảng (Ngày 1) bao gồm việc thiết lập giao diện người dùng cơ bản (nhập URL, lưu Gemini API Key vào LocalStorage) và endpoint backend để xác thực kết nối tới Gemini API. Điều này đảm bảo toàn bộ luồng truyền thông tin từ client qua backend lên Gemini hoạt động thông suốt trước khi phát triển các tính năng phức tạp hơn.

## What Changes

- **Backend**:
  - Thêm class `GeminiService` tại `backend/app/services/gemini.py` để kết nối Gemini API.
  - Thêm endpoint POST `/api/v1/gemini/test` tại `backend/app/api/v1/endpoints/gemini.py` để chạy thử nghiệm prompt kết nối.
  - Đăng ký router mới vào hệ thống router chung của FastAPI.
- **Frontend**:
  - Cập nhật giao diện chính `frontend/src/App.tsx` với bố cục hiện đại: ô nhập API Key (lưu LocalStorage), ô test prompt kết nối Gemini, và ô nhập URL YouTube (chờ xử lý Ngày 2).
  - Thêm API service để gọi backend test kết nối.

## Capabilities

### New Capabilities
- `youtube-script-ai`: Tích hợp Gemini API và giao diện cấu hình API Key, nhập URL video.

### Modified Capabilities

## Impact
- Tạo mới các file backend liên quan tới Gemini Service và API endpoint.
- Cập nhật file định tuyến backend `backend/app/api/v1/router.py`.
- Thay đổi hoàn toàn file frontend `frontend/src/App.tsx` và thêm file service frontend.
