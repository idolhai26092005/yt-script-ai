## Context

Dự án YouTube Script AI Generator cần bước đệm để đảm bảo tích hợp Gemini API hoạt động ổn định giữa Frontend, Backend và AI API. Thiết lập ban đầu bao gồm việc cấu hình khoá API và kiểm tra kết nối thông qua một giao diện đơn giản.

## Goals / Non-Goals

**Goals:**
- Tích hợp thành công thư viện `google-generativeai` ở backend.
- Tạo API test kết nối `/api/v1/gemini/test` chấp nhận API Key động từ request header.
- Xây dựng giao diện Frontend hoàn chỉnh cho Ngày 1: cấu hình API Key, form test prompt và input URL YouTube (có validation).
- Lưu trữ API Key an toàn trong localStorage của người dùng.

**Non-Goals:**
- Chưa xử lý lấy transcript của YouTube (sẽ làm ở Ngày 2).
- Chưa sinh kịch bản song ngữ thực tế từ video (sẽ làm ở Ngày 3).

## Decisions

### 1. Truyền Gemini API Key qua request header thay vì lưu cố định ở Backend
- **Giải pháp**: Frontend gửi key qua header `X-Gemini-API-Key` mỗi khi gọi API. Backend đọc header này để khởi tạo `genai.configure(api_key=...)` động cho từng request.
- **Lý do**: Đảm bảo bảo mật, người dùng tự cung cấp key của họ, tránh việc server phải lưu trữ key cá nhân.

### 2. Sử dụng Gemini 1.5 Flash làm model mặc định
- **Giải pháp**: Dùng model `gemini-1.5-flash` để xử lý các prompt test và sinh kịch bản sau này.
- **Lý do**: Chi phí rẻ (miễn phí ở giới hạn free tier), tốc độ phản hồi nhanh, context window lớn (1M tokens).

### 3. Giao diện Frontend dùng React + Tailwind CSS
- **Giải pháp**: Xây dựng UI dạng Single Page, chia làm 2 phần chính: panel cấu hình (API Key, test prompt) và panel nhập liệu chính (YouTube URL).
- **Lý do**: Tailwind CSS đã được tích hợp sẵn bằng `@tailwindcss/vite`, giúp tạo nhanh giao diện tối (Dark mode) sang trọng, hiện đại.

## Risks / Trade-offs

- **Rủi ro**: Người dùng nhập API Key sai hoặc hết hạn.
- **Giải pháp**: Backend bắt lỗi `google.api_core.exceptions.GoogleAPICallError` hoặc `ValueError` khi khởi tạo và trả về mã lỗi HTTP 400 kèm thông báo rõ ràng cho client hiển thị lên UI.
