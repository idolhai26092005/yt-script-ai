## Context

Dự án YouTube Script AI yêu cầu thiết lập cấu trúc thư mục tiêu chuẩn cho cả backend (FastAPI) và frontend (React + Vite + TS + Tailwind CSS).

## Goals / Non-Goals

**Goals:**
- Tạo cấu trúc thư mục backend chuẩn FastAPI.
- Tạo cấu trúc thư mục frontend chuẩn React + Vite + TS + Tailwind.
- Tạo các file cấu hình cần thiết để khởi chạy dự án (`package.json`, `requirements.txt`, `vite.config.ts`, `.env`, `main.py`).

**Non-Goals:**
- Viết mã nguồn nghiệp vụ thực tế hoặc giao diện hoàn chỉnh.
- Triển khai kết nối database hoặc dịch vụ ngoài.

## Decisions

### Decision 1: Cấu trúc thư mục backend
Backend sử dụng cấu trúc FastAPI chia lớp:
- `app/api`: Chứa các API endpoint và router.
- `app/core`: Chứa config, bảo mật và thiết lập môi trường.
- `app/crud`, `app/models`, `app/schemas`: Chuẩn bị sẵn cho việc kết nối DB sau này.
- `app/services`: Chứa logic nghiệp vụ xử lý chính (gọi Gemini, fetch transcript).

### Decision 2: Cấu trúc thư mục frontend
Frontend sử dụng React + Vite + TypeScript với CSS Tailwind:
- `src/features`: Tổ chức mã nguồn theo nghiệp vụ (ví dụ: dashboard, script-generator).
- `src/components`: Thành phần giao diện dùng chung (buttons, inputs, v.v.).
- `src/services`: Chức năng gọi API đến FastAPI backend.

## Risks / Trade-offs

- **Risk**: Xung đột phiên bản node hoặc python trên máy local.
- **Mitigation**: Cố định phiên bản trong `package.json` và chỉ định thư viện cụ thể trong `requirements.txt`.
