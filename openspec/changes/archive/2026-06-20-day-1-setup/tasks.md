## 1. Backend Implementation

- [x] 1.1 Tạo `GeminiService` tại `backend/app/services/gemini.py` tích hợp `google-generativeai`.
- [x] 1.2 Tạo endpoint POST `/api/v1/gemini/test` tại `backend/app/api/v1/endpoints/gemini.py` để test kết nối, đọc `X-Gemini-API-Key` từ header.
- [x] 1.3 Đăng ký router `gemini_endpoints` vào `backend/app/api/v1/router.py`.

## 2. Frontend Implementation

- [x] 2.1 Tạo `frontend/src/services/api.ts` để gọi API Backend và truyền API Key.
- [x] 2.2 Cập nhật giao diện `frontend/src/App.tsx` với thiết kế hiện đại, hỗ trợ lưu API Key vào LocalStorage, test kết nối Gemini và validate URL YouTube.
